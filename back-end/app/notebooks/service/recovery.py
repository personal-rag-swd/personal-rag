"""Startup recovery for reports left mid-flight by a crash or restart.

Reports stuck in ``pending``/``generating`` are re-queued (or failed if their
notebook/user/context is gone) so a restart never strands a report forever.
Invoked once from the application lifespan.
"""

import asyncio
import logging

from app.notebooks.models import Notebook, NotebookReport
from app.notebooks.service.reports import build_report_context, run_report_generation
from app.users.models import User

logger = logging.getLogger("app.startup")

# Hold strong references to fire-and-forget recovery tasks so they aren't
# garbage-collected mid-flight; each removes itself on completion.
_recovered_tasks: set[asyncio.Task[None]] = set()


async def recover_pending_reports() -> None:
    try:
        stuck_reports = await NotebookReport.find(
            {"status": {"$in": ["pending", "generating"]}}
        ).to_list()

        if not stuck_reports:
            return

        logger.info(
            "Recovering %d pending/generating report(s) after restart",
            len(stuck_reports),
        )

        for report in stuck_reports:
            if report.status == "generating":
                report.status = "pending"
                await report.save()

            notebook = await Notebook.find_one({"_id": report.notebook_id})
            user = await User.find_one({"_id": report.user_id})
            if notebook is None or user is None:
                logger.warning(
                    "Skipping report %s: notebook or user not found",
                    report.id,
                )
                report.status = "failed"
                report.error_message = (
                    "Recovery failed: associated notebook or user no longer exists."
                )
                await report.save()
                continue

            context = await build_report_context(notebook, user)
            if not context:
                logger.warning(
                    "Skipping report %s: no indexed documents available for context",
                    report.id,
                )
                report.status = "failed"
                report.error_message = "Recovery failed: no indexed documents found."
                await report.save()
                continue

            task = asyncio.create_task(
                run_report_generation(
                    report_id=report.id,
                    report_type=report.report_type,
                    context=context,
                    instructions=report.additional_instructions,
                    detail_level=report.detail_level,
                )
            )
            _recovered_tasks.add(task)
            task.add_done_callback(_recovered_tasks.discard)
            logger.info("Re-queued report %s (type=%s)", report.id, report.report_type)
    except Exception:
        logger.exception("Failed to recover pending reports")
