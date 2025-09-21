# Chatbot Multi-turn Flow Test Plan (Active)

Last updated: 2025-08-26

This is the single source of truth for our current testing effort. We will update this section and our internal memory after each task completion.

---

## How We Work This Plan

- We execute tasks strictly in order, marking them here when done.
- We keep this plan and Cascade memory in sync after each step.
- Live tests are gated by env flags and skip automatically when not configured.
- All integration tests use the real stack (no mocks/stubs). If required services are unavailable, tests will skip via gating rather than simulate responses.

---

## Immediate Focus (Pre-main plan)

We will address the following three fallback-robustness patches first, then resume the main plan tasks below.

1) Expand category synonym coverage or drive from catalog metadata
   - Scope: In `router/intent_classifier.py` fallback mode only, broaden synonym mapping for categories (e.g., phones/mobiles/cellphone → smartphones). Prefer loading synonyms from catalog/config if available.
   - Acceptance: Queries using common variants map to canonical categories present in the catalog. No impact on LLM closed-set paths.
   - Tests: Live-gated integration tests in `test/test_multiturn_flow.py` exercising category variants; skip when env not configured.

2) Make heuristic lists configurable
   - Scope: Externalize keyword lists (intent detection), generic noun list for brand cleanup, and phrase/pattern lists for rating/stock/discount so they can be tuned without code changes via repo-local config.
   - Acceptance: Lists can be adjusted via the repo-local file `fallback_config/heuristics.json` (single source of truth). No env/S3 overrides. Behavior remains unchanged when the file is absent (defaults apply).
   - Tests: Smoke validation via live tests; ensure defaults still pass.

3) Add fuzzy match for brand/category in fallback mode only
   - Scope: When LLMs are unavailable and exact/synonym matches fail, apply conservative fuzzy matching to map user input to canonical brand/category. Keep strict equality in LLM closed-set flows.
   - Guardrails: Exact match wins; apply thresholds and tie-break rules; abstain on ambiguous matches.
   - Tests: Live-gated tests with mild typos (e.g., "Aplpe") validating canonicalization in fallback.

---

## Scope (Flows to Validate)

- SEARCH (entity-extracted filters: brand, category, price_min/max, rating_min, in_stock, discount_min, tags)
- REFINE (multi-turn continuation using session memory and heuristics)
- COMPARE (uses last_search_results)
- SUPPORT (RAG with citations)
- RECOMMENDATION
- CART

---

## Environment & Flags

- Required services: Redis, Pinecone (products/support), HF API, AWS S3 (for support KB)
- Required env (examples): PINECONE_API_KEY, PINECONE_PRODUCTS_INDEX, PINECONE_SUPPORT_INDEX, HF_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME, REDIS_HOST or REDIS_URL
- Test gating: RUN_LIVE_TESTS=1; new: RUN_LIVE_MEMORY_TESTS=1 (for multi-turn memory suite)
- Optional flags: SEARCH_RERANK_ENABLED, SEARCH_TAGS_SERVER_FILTER_ENABLED, SEARCH_CASE_INSENSITIVE, DISABLE_RATE_LIMITING

---

## Tasks (Current Plan)

- [x] 0) Repo hygiene
  - Deleted all existing tests under `test/`.
  - Created single integration test file: `test/test_multiturn_flow.py`.
- [x] Search intent UX guardrails (surface fallback)
  - Integrated surface-level fallback detection in tests and prompt/context guard in code to avoid false apologies when results exist.
  - Validated live on 2025-08-25: 14 passed, 6 skipped with `RUN_LIVE_TESTS=1` and `RUN_LIVE_MEMORY_TESTS=1`.
- [x] 1) Core multi-turn scenario (session: demo1)
  - Scope: SEARCH → REFINE (in-stock → cheaper → higher rating) → FOLLOW-UP → COMPARE → SUPPORT in one session to exercise memory.
  - Guardrails: No surface fallback phrasing when products are returned (response/suggestions). Truthful "no results" allowed when a refine yields none.
  - Gating: `RUN_LIVE_TESTS=1`, `RUN_LIVE_MEMORY_TESTS=1`; uses real Pinecone/Redis/S3/HF stack.
  - Repro:
    - Single: `RUN_LIVE_TESTS=1 RUN_LIVE_MEMORY_TESTS=1 DISABLE_RATE_LIMITING=1 pytest -q test/test_multiturn_flow.py::test_core_multi_turn_session_demo1`
    - Full: `RUN_LIVE_TESTS=1 RUN_LIVE_MEMORY_TESTS=1 DISABLE_RATE_LIMITING=1 pytest -q test/test_multiturn_flow.py`
  - Result: 15 passed, 5 skipped (live). No fallback detected when products existed. In-stock refine returned zero items in this run; acceptable.

- [x] 1.5) Greeting and Mid-Conversation Handling
  - Scope: Added GREETING intent detection and context-aware responses for both initial greetings and mid-conversation social messages.
  - Implementation: 
    - Enhanced LLM prompts to recognize greeting patterns
    - Added keyword-based fallback for simple greetings
    - Created `handle_greeting` function with context-aware responses
    - Integrated with conversation memory for session awareness
  - Documentation: See `docs/GREETING_IMPLEMENTATION.md` for details

- [ ] 2) Memory isolation & TTL
  - New session (demo2) repeats steps 1–2 without leaking from demo1.
  - Fresh session (demo3) sends "compare first and second" → helpful guidance to search first.
  - Verify Redis keys `conv:<session>` and `ctx:<session>` exist with TTL ≤ 86400 (best-effort, skip if Redis not accessible in test context).

- [ ] 3) Edge scenarios
  - Brand change mid-flow: user switches to another brand → verify brand persistence doesn’t lock user to previous brand.
  - Category fallback after empty refine: verify in-memory baseline filtering and secondary category-constrained search path can recover results.
  - Degraded-mode optional: simulate Pinecone unavailable → keyword fallback parity; SUPPORT no citations.

- [ ] 4) Observability & health (best-effort)
  - `/health` shows Redis and Pinecone connectivity (or degraded).
  - SUPPORT analytics keys increment best-effort in Redis.

- [ ] 5) Manual QA script
  - Provide cURL sequence for all steps using a stable `session_id`.

- [ ] 6) Execution & gating
  - Tests auto-skip unless `RUN_LIVE_TESTS=1` and `RUN_LIVE_MEMORY_TESTS=1` are set with required creds.

- [ ] 7) Sync procedure
  - After each completed task: mark it here, update Cascade memory, and keep notes of any flakiness or data quirks.

---

## Acceptance Criteria

- Correct filtering for brand/category/price/rating/stock/discount/tags.
- Reranking preference applied when enabled.
- REFINE updates results coherently and persists brand when appropriate.
- COMPARE returns two products with a clear summary and uses the current session context.
- SUPPORT answers include a short citation when RAG active; degrade gracefully otherwise.
- No long-term personalization beyond session TTL; sessions remain isolated.

---

## Manual QA – Example cURL (reference)

Use `session_id=demo1` and POST to `/chat` with JSON bodies matching the steps above. Repeat with demo2/demo3 for isolation checks.

---

## Notes

- This section supersedes all previous plans. Older content has been removed.
