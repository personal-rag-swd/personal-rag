# TODO — PDF images in RAG: finish & harden "View Source shows the image"

Goal: the chat agent reads images embedded in PDFs, cites them like text
sources, and clicking a citation's **View source** shows the actual image.

## Current state (verified 2026-07-14)

Most of this feature already exists — do **not** re-implement it:

**Committed:**
- `back-end/app/notebooks/rag/image_ingestion.py` — extracts embedded PDF
  images (≥64px, deduped by xref), uploads them to S3 under
  `<doc prefix>/images/img_<xref>.<ext>`, describes each with the vision LLM
  (bounded concurrency), and emits `chunk_type="image"` chunk Documents with
  `s3_key` / `media_type` metadata. Wired into ingestion for `.pdf` in
  `ingestion_service.py:_build_split_documents` (runs concurrently with text
  chunking); standalone image uploads go through the same
  `build_image_chunk_document` path.
- `agent/chat_agent.py` — `search_notebook_context` downloads retrieved image
  chunks' bytes and attaches them to the tool return as `BinaryContent`, each
  prefixed with an `image_part_label` so the model can cite what it sees.
- `GET /notebooks/{id}/documents/{doc_id}/chunks/{i}/image-url`
  (`service/chunks.py:build_chunk_image_url`) — presigned GET URL for an image
  chunk, ownership-checked, using `s3_public_endpoint_url`.
- `front-end/src/components/assistant-ui/markdown-text.tsx` — the whole
  citation UI: `CitationPopover` renders the image inline for
  `chunk_type === "image"` sources; **View source** opens
  `DocumentChunksViewer`, which renders image chunks via `ImageChunkDisplay`
  (presigned URL) with the description as caption, auto-scrolled/highlighted.

**Uncommitted (in flight, working tree):** S-label citations — `SOURCE S3 [...]`
headers + `[S3]` citation form (`context_prompts.py`, `system_prompts.py`,
`chat_agent.py`), `source_number` resolution in `memory/transcript.py` and
`schemas.py`/`api.ts`, frontend `#citeS/` handling in `markdown-text.tsx`,
tests in `tests/test_notebook_prompts.py` + new
`tests/test_chat_transcript_references.py`.

Validation status of the in-flight work (all run 2026-07-14):
`pytest tests/test_notebook_prompts.py tests/test_chat_transcript_references.py`
✅ 10 passed · `ruff check app tests` ✅ · `pyright` ✅ 0 errors ·
`npm run typecheck` ✅ · `npm run lint` ✅.

---

## Phase 1 — Land the in-flight S-label citation work

- [x] Full backend suite green: `uv run pytest --ignore=tests/billing`
      (billing hits the live Polar sandbox — always excluded on a clean tree).
      ✅ 148 passed (2026-07-14).
- [ ] Manual E2E smoke (see **Verification** below) — especially the *live
      streaming* path, which resolves citations by regex-parsing the tool
      result text (`SOURCE_BLOCK_REGEX` in `markdown-text.tsx`) before the
      persisted `metadata.custom.sources` exists.
- [ ] Commit the working tree (backend S-labels + frontend citeS rendering
      belong in one commit — the SOURCE grammar changed on both sides).

## Phase 2 — Page numbers on image chunks

Image chunks currently record no page; the label "image on page N" is only
used as a vision-fallback string. Users can't tell where a cited figure lives.

- [ ] `image_ingestion.py:_collect_pdf_images` — return the (1-based) page
      number per image; thread it through `extract_pdf_images`.
- [ ] `build_image_chunk_document` — accept optional `page_number: int | None`
      and store it in chunk metadata (stays `None` for direct image uploads).
      No Atlas index change needed (metadata is not a `$vectorSearch` filter
      path).
- [ ] `context_prompts.py` — include ` page=N` in the image `SOURCE` header and
      `image_part_label` so the model can say "the chart on page 4".
      ⚠️ This file is the single owner of the SOURCE grammar: update
      `_SOURCE_BLOCK_PATTERN` **and** the mirrored `SOURCE_BLOCK_REGEX` in
      `markdown-text.tsx` in the same change, plus grammar tests in
      `tests/test_notebook_prompts.py`.
- [ ] `chunk_to_source` — carry `page_number` inside the source `metadata`
      dict (schemas already pass `metadata` through to the frontend).
- [ ] Frontend — show a small "Page N" badge in `CitationPopover` and on
      image chunks in `DocumentChunksViewer` when
      `metadata.page_number` is present.
- [ ] Note in the PR: existing indexed documents won't have `page_number`
      until re-ingested — treat it as optional everywhere. (Re-upload
      re-indexes; no migration needed.)

## Phase 3 — Viewer ordering: images in reading position

Today image chunks are appended after all text chunks
(`_build_split_documents` does `split_docs + image_docs`), so the View Source
dialog shows every figure at the end of the document instead of near its page.

Recommended approach — per-page text extraction so text chunks also know
their page:

- [ ] `document_chunker.py:_extract_pdf_text` — switch to
      `pymupdf4llm.to_markdown(doc, page_chunks=True)` to get per-page
      markdown (keep the image-placeholder stripping per page).
- [ ] Record `page_number` (page where the chunk starts) in text-chunk
      metadata. Two options; pick after a quick spike:
      1. Split per page (simple; loses chunk overlap across page
         boundaries — usually acceptable), or
      2. Keep whole-document splitting and map each chunk's `start_index`
         back to a page via cumulative page offsets (preserves overlap;
         slightly fiddlier).
- [ ] `ingestion_service.py:_build_split_documents` — stable-sort
      `text_docs + image_docs` by `(page_number, is_image)` before
      `chunk_index` assignment so figures land in reading position.
      Non-PDF formats are unaffected (no page metadata → original order).
- [ ] Check retrieval-affecting invariants: chunk contents don't change, only
      order/metadata — embeddings and search behavior stay identical.
- [ ] Fallback if the spike shows page mapping is unreliable: keep current
      order but render a "Figures" section separator in
      `DocumentChunksViewer` with the Phase 2 page badges — cheap and still a
      big UX win.

## Phase 4 — Reports read the actual images

`service/reports.py` already feeds image chunks' *descriptions* into report
context via `source_block`, but never attaches the image bytes — reports are
generated blind to what charts actually show.

- [ ] Extract the image-fetch logic from `chat_agent.py`
      (`_fetch_image_content` + the label-then-bytes parts assembly) into a
      shared helper, e.g. `rag/image_context.py`:
      `build_image_parts(chunks, store) -> list[str | BinaryContent]`.
      `chat_agent.search_notebook_context` becomes a thin caller.
- [ ] In `run_report_generation`'s context assembly, append the image parts
      after the source blocks, capped by a new setting
      (e.g. `notebook_report_max_images`, default ~10) so image-heavy
      notebooks don't blow the report's token budget.
- [ ] Pass the multimodal parts list as the report agents' user prompt
      (pydantic-ai accepts `list[str | BinaryContent]` — same as chat).
- [ ] Tests: stub `resolve_chat_provider` with `TestModel` (report/chat tests
      must never hit the network) and assert image parts are attached and
      capped.
- [ ] Non-goal (this pass): clickable citations inside rendered reports —
      report output is structured content with no citation UI today.

## Phase 5 — Hardening & cleanup

- [ ] Add the repo-root `.tmp/` directory to ruff's exclude (root
      `uv run ruff check` currently reports ~9.8k errors from it; `app`/
      `tests` are clean). One line in `back-end/pyproject.toml`.
- [ ] Presigned-URL expiry: an image `<img>` that fails (e.g. URL expired in
      a long-open tab) is hidden permanently (`markFailed`). Add a single
      refetch-once-on-error to `useChunkImageUrl` before giving up.
- [ ] `preprocessCitations` legacy verbose-form parsing in
      `markdown-text.tsx` is now only needed for pre-S-label histories — add
      a comment marking it legacy; consider removal once old transcripts age
      out (do not remove now).
- [ ] Known minor limitation to document (no fix needed): an image reused on
      several PDF pages is indexed once (deduped by xref) and labeled with
      its first page.

## Verification

Backend (needs local MongoDB :27017 + MinIO :9000, `minioadmin`/`minioadmin`):
```
cd back-end
uv run pytest --ignore=tests/billing
uv run ruff check app tests && uv run ruff format --check app tests
npx pyright --pythonpath .venv/bin/python
```

Frontend (no test runner):
```
cd front-end && npm run typecheck && npm run lint
```

Manual E2E (each phase):
1. `docker compose up --build` (or dev servers), upload a PDF containing
   charts/figures; wait for status `indexed`; confirm
   `<prefix>/images/img_*.{png,jpeg}` objects exist in MinIO and image chunks
   appear in `GET .../documents/{id}/chunks`.
2. Ask a question answerable only from a figure ("what does the chart on
   page N show?"). Confirm the answer cites the image source (`[S…]` badge).
3. Click the citation badge → popover shows the image + description (with
   page badge after Phase 2).
4. Click **View source** → dialog opens, scrolls to the highlighted image
   chunk, image renders (positioned near its page after Phase 3).
5. Repeat 2–4 both mid-stream (live) and after a page reload (persisted
   history path) — the two paths resolve sources differently.
6. After Phase 4: generate a briefing-doc report on the same notebook and
   confirm figure-only facts appear in it.
