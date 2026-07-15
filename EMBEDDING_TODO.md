# Embed image chunks directly with multimodal embeddings (Gemini via OpenRouter)

## Context

Today, image chunks (standalone image uploads + images embedded in PDFs) get their retrieval vector by first describing the image with a vision LLM (`describe_image`) and embedding that text. Goal: embed images **directly** — OpenRouter's embeddings API supports multimodal input ([docs](https://openrouter.ai/docs/api/reference/embeddings#image-input)), and the already-configured model `google/gemini-embedding-2` embeds text and images into one unified vector space (1536 dims supported → **no Atlas index change**, same provider, same API key).

Chosen approach (enterprise dual-representation pattern):
- The image chunk's vector comes from the **image bytes** via OpenRouter multimodal embeddings.
- **Keep** the short vision-LLM caption in `content` — display/caption/SOURCE-block use only (future reranking/hybrid-search value), no longer the embedding input.
- Add provenance metadata `embedding_source: "image" | "text"` to every chunk.
- **New uploads only** — no backfill of existing chunks.

Citations/references are unaffected: S-labels, presigned image-URL viewer, and image-bytes attachment to chat/report prompts all read `chunk_metadata` + S3, never the embedding.

## Known unknown (resolve first)

OpenRouter's embeddings docs show the multimodal input shape
`input: [{"content": [{"type": "image_url", "image_url": {"url": ...}}]}]`
but only with public URLs. Verify with **one live call** early in Step 1 that:
1. base64 `data:{media_type};base64,...` URIs are accepted (standard on their chat API), and
2. the OpenAI SDK's `embeddings.create` accepts dict-shaped `input` (it's typed `str | list[str] | tokens`). If it rejects dicts or the ignore fights pyright/ruff, use the raw typed call instead:
   `await provider.client.post("/embeddings", cast_to=openai.types.CreateEmbeddingResponse, body={...})`.

Base64 data URIs are the **only** transport (decision made): presigned MinIO URLs would point at localhost in local dev and be unreachable by OpenRouter. If data URIs are rejected outright, the fallback design below still ships safely (every image degrades to today's behavior with a log warning) — but flag it.

## Changes

### 1. `back-end/app/core/embedding_provider.py` — add `embed_image`

- [ ] Extract the request core of `embed_texts.embed_batch` (semaphore + `TransientProviderError` translation for 429/connection/5xx + sort by index) into a shared private helper, e.g. `async def _create_embeddings(input_payload: object) -> list[list[float]]`.
- [ ] `embed_texts` keeps its exact signature/batching (batches of 96) — text path byte-for-byte unchanged.
- [ ] New: `async def embed_image(data: bytes, media_type: str) -> list[float]` — builds the base64 data-URI payload above, one image per request (images are token-heavy; per-request isolation enables per-image fallback), concurrency bounded by the existing `_embed_semaphore`.

### 2. `back-end/app/notebooks/rag/image_ingestion.py` — carry bytes to embed time

- [ ] Module constant `EMBED_IMAGE_BYTES_KEY = "_embed_image_bytes"` — transient metadata key, popped before persistence (bytes must never reach Mongo).
- [ ] `build_image_chunk_document(...)` gains required keyword `image_bytes: bytes`, stored under that key. Memory cost is nil — the bytes already exist in `extract_pdf_images`'s `images` list; this adds a reference.
- [ ] `extract_pdf_images` (~L204-216): pass `image_bytes=data` (the bytes are the 2nd tuple element, currently discarded in the zip).
- [ ] `describe_image` stays as-is (caption kept per the enterprise pattern).

### 3. `back-end/app/notebooks/rag/ingestion_service.py` — embed images from bytes, fallback, provenance

- [ ] Standalone-image branch of `_build_split_documents` (~L154): pass `image_bytes=body`.
- [ ] Rework `_embed_and_persist_chunks` (L197-244):
  - Pop `EMBED_IMAGE_BYTES_KEY` from every doc's metadata **up front, unconditionally** (`chunk_metadata=split_doc.metadata` is persisted verbatim at L238, so the pop is what keeps bytes out of Mongo).
  - Text chunks: unchanged single `embed_texts(...)` call + existing length-mismatch check; keep the "unusually small text" warning computed over all `page_content` as today.
  - Image chunks: `asyncio.gather` over a helper:
    ```python
    async def _embed_image_or_fallback(doc, image_bytes) -> tuple[list[float], str]:
        # TransientProviderError propagates → whole document re-queues (same as text today).
        # Any other failure (e.g. 400 bad payload) → log warning, embed the
        # description text instead, return ("text" provenance).
    ```
  - Merge vectors back by **original index** (PDF chunks are interleaved by `_order_pdf_chunks` — don't assume partitioned order).
  - Persist `chunk_metadata={**split_doc.metadata, "embedding_source": source}` — `"text"` for text chunks and fallbacks, `"image"` for successful direct embeds.
- [ ] No change to `ingest_document_by_id` error handling — `TransientProviderError` already re-queues via the existing catch.

### 4. No changes (verified)

`search_service.py` (text query in the unified space is the point), citation grammar/`image_context.py`, chunk viewer endpoints, report image attachment, Atlas index (`embedding_source` is not a `$vectorSearch` filter path), frontend.

## Tests (`back-end/tests/`)

Follow the existing style in `test_ingestion_service.py` (monkeypatch `ingestion_service.embed_texts` / `describe_image` / new `embed_image`; `patch.object` on `NotebookDocumentChunk`; real MongoDB `personal-rag-test` + MinIO required):

- [ ] Update `test_run_document_ingestion_embeds_chunks`: assert text chunks get `embedding_source == "text"`.
- [ ] New: standalone image upload → `embed_image` called with raw body + media type; chunk has caption in `content`, `embedding_source == "image"`, and `EMBED_IMAGE_BYTES_KEY not in chunk_metadata`.
- [ ] New: `embed_image` raises non-transient error → document still indexes, chunk falls back with `embedding_source == "text"`, `embed_texts` called with the description.
- [ ] New: `embed_image` raises `TransientProviderError` → propagates / document re-queues as `uploaded`.
- [ ] New: `build_image_chunk_document(..., image_bytes=b"abc")` stores bytes under the transient key (in `test_image_ingestion.py` or alongside existing chunker tests).
- [ ] New provider test: `embed_image` payload shape (fake provider client recording the call — patch `_get_provider` itself, minding its `lru_cache`) and 429 → `TransientProviderError`.

Skip `tests/billing` (hits live Polar). Chat/report tests untouched — citation machinery doesn't read embeddings.

## Verification

From `back-end/`: `uv run pytest --ignore=tests/billing`, `uv run ruff check`, `uv run ruff format`, `npx pyright --pythonpath .venv/bin/python`.

End-to-end: run the dev server, upload a PDF containing images to a notebook, confirm the document reaches `indexed`, inspect a stored image chunk (`embedding_source == "image"`, no `_embed_image_bytes` key, caption present), then chat with a query targeting the image content and confirm the image citation popover + "View source" still render the image.
