from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.event_bus import DomainEvent, DomainEventBus
from app.event_listeners import register_default_event_listeners
from app.notebooks.domain_events import DocumentIndexed, ReportCompleted
from app.notebooks.events import event_bus
from app.notebooks.listeners import project_document_event
from app.notebooks.models import NotebookDocument, NotebookReport

pytestmark = pytest.mark.anyio


class _Base(DomainEvent):
    pass


class _Child(_Base):
    pass


class _Sibling(DomainEvent):
    pass


async def test_emit_dispatches_to_exact_and_base_class_listeners() -> None:
    bus = DomainEventBus()
    received: list[str] = []

    async def on_base(_event: DomainEvent) -> None:
        received.append("base")

    async def on_child(_event: DomainEvent) -> None:
        received.append("child")

    async def on_sibling(_event: DomainEvent) -> None:
        received.append("sibling")

    bus.subscribe(_Base, on_base)
    bus.subscribe(_Child, on_child)
    bus.subscribe(_Sibling, on_sibling)

    await bus.emit(_Child())

    # Base-class listener sees the subclass; the sibling listener never fires.
    assert sorted(received) == ["base", "child"]


async def test_listener_registered_on_two_levels_runs_once() -> None:
    bus = DomainEventBus()
    calls = 0

    async def listener(_event: DomainEvent) -> None:
        nonlocal calls
        calls += 1

    bus.subscribe(_Base, listener)
    bus.subscribe(_Child, listener)

    await bus.emit(_Child())

    assert calls == 1


async def test_failing_listener_is_isolated_and_siblings_still_run() -> None:
    bus = DomainEventBus()
    order: list[str] = []

    async def boom(_event: DomainEvent) -> None:
        order.append("boom")
        error = "listener failure"
        raise RuntimeError(error)

    async def after(_event: DomainEvent) -> None:
        order.append("after")

    bus.subscribe(_Base, boom)
    bus.subscribe(_Base, after)

    await bus.emit(_Base())  # does not raise

    assert order == ["boom", "after"]


async def test_critical_listener_failure_propagates() -> None:
    bus = DomainEventBus()

    async def boom(_event: DomainEvent) -> None:
        error = "critical failure"
        raise RuntimeError(error)

    bus.subscribe(_Base, boom, critical=True)

    with pytest.raises(RuntimeError, match="critical failure"):
        await bus.emit(_Base())


async def test_subscribe_is_idempotent() -> None:
    bus = DomainEventBus()
    calls = 0

    async def listener(_event: DomainEvent) -> None:
        nonlocal calls
        calls += 1

    bus.subscribe(_Base, listener)
    bus.subscribe(_Base, listener)

    await bus.emit(_Base())

    assert calls == 1


async def test_subscribe_rejects_conflicting_critical_flag() -> None:
    bus = DomainEventBus()

    async def listener(_event: DomainEvent) -> None:
        return None

    bus.subscribe(_Base, listener, critical=True)

    # Same callable on a different MRO level with a different critical flag would
    # leave emit's dedup silently honoring only one flag — reject it instead.
    with pytest.raises(ValueError, match="critical"):
        bus.subscribe(_Child, listener, critical=False)


async def test_document_indexed_projects_onto_sse_bus() -> None:
    user_id = uuid4()
    notebook_id = uuid4()
    document = NotebookDocument(
        notebook_id=notebook_id,
        user_id=user_id,
        filename="paper.txt",
        status="indexed",
        content="hello",
    )

    async with event_bus.subscribe(user_id) as queue:
        await project_document_event(DocumentIndexed(document))
        event = queue.get_nowait()

    assert event["type"] == "document_update"
    assert event["notebook_id"] == str(notebook_id)
    assert event["document"]["status"] == "indexed"


async def test_registered_default_listeners_project_report_events() -> None:
    register_default_event_listeners()
    from app.core.event_bus import domain_event_bus

    user_id = uuid4()
    notebook_id = uuid4()
    report = NotebookReport(
        notebook_id=notebook_id,
        user_id=user_id,
        report_type="briefing",
        status="completed",
        content={"summary": "done"},
    )

    async with event_bus.subscribe(user_id) as queue:
        await domain_event_bus.emit(ReportCompleted(report))
        event = queue.get_nowait()

    assert event["type"] == "report_update"
    assert event["notebook_id"] == str(notebook_id)
    assert event["report"]["status"] == "completed"
