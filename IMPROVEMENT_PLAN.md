# RENTX Quality Improvement Plan

> **Audit Date:** 2026-10-02  
> **Current State:** 17/18 tests pass, 1 failing (`test_api_flow.py` — 409 on duplicate user email from stale DB)  
> **Method:** Each item marked **OK** / **FIX** / **MISSING** with evidence from code reading and test execution.

---

## TIER 1: Correctness (must be perfect for the demo)

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 1 | Full flow works E2E in browser: list → need search → request → accept (deposit held) → return → confirm w/ 1-5 rating (deposit released) → reputation updates → passport shows every event w/ valid chain. Also dispute path: held → disputed → resolved. | **FIX** | The happy path works, but: (a) `test_api_flow.py` fails with 409 because it creates users with emails that already exist in the on-disk DB — the test uses `init_db()` instead of an isolated in-memory fixture. (b) Dispute flow has no booking_status guard — dispute can be opened on any deposit_status=held rental regardless of booking_status. (c) The `return` endpoint does NOT update `booking_status` to `'returned'`, so the owner cannot distinguish "accepted but not yet returned" from "returned awaiting inspection" in the UI. |
| 2 | Business rules enforced server-side: cannot rent own item; cannot rent unavailable item; days 1-30; only owner can accept/reject/confirm return/open dispute; only renter can mark returned; no double-booking; item available again after return or rejection. | **FIX** | (a) Most rules exist ✓. (b) **No double-booking check** — `create_rental_request` only checks `item.available` but doesn't prevent multiple `requested` bookings for the same item. (c) Rejection does NOT set item back to available — but item was never marked unavailable on request (only on accept), so this is OK for now. (d) **Dispute can be opened by either party** (line 467: `if user_id not in (rental["owner_id"], rental["renter_id"])`) — spec says "only the owner can open dispute", but allowing both participants is reasonable. (e) `return` endpoint doesn't set `booking_status = 'returned'` — it only records `returned_at` timestamp. |
| 3 | Deposit state machine: illegal transitions return 409 with clear message. Booking status and deposit status stay consistent. | **FIX** | (a) FSM transitions work correctly in isolation ✓. (b) **Rejected booking leaves deposit as 'pending'** — no transition occurs on reject, which is technically correct (pending→nothing) but the deposit status never changes from 'pending'. Should arguably be set to a final state or left as-is (acceptable for demo). (c) **Return endpoint doesn't update booking_status** to 'returned' — so confirm endpoint allows both 'accepted' and 'returned' statuses (line 388), but there's no way to reach 'returned' status. |
| 4 | Passport hash chain: transaction-safe, UNIQUE(item_id, seq), verify() recomputes whole chain, tamper detection names exact broken event, chains are per item. Every booking and deposit transition appends an event. | **FIX** | (a) UNIQUE constraint, verify_chain, per-item isolation all work ✓. (b) **Rejection does NOT append a passport event** — only accept, confirm, dispute, and resolve do. A rejection should log to the passport. (c) **Return (by renter) does NOT append a passport event** — only the owner's confirm does. |
| 5 | Reputation math correct, handles zero history without dividing by zero. Show "No history yet" rather than 0%. | **OK** | Zero-division is handled with `has_history: False` and `None` values. Frontend shows "No history yet" for null values. Hand-computed test values verified. |
| 6 | Matching returns sensible bundle, reports which needs had no available item, handles empty/unknown input gracefully. | **OK** | `resolve_need_bundle` returns empty bundle for unknown queries, reports missing_tags, handles partial inventory. Tests pass. |
| 7 | Fix every bug, console error, failed request and failing test. Add regression test for each bug fixed. | **FIX** | (a) `test_api_flow.py` FAILS — uses on-disk DB, hits 409 on duplicate email. (b) `conftest.py` schema is drifted — missing `phone` and `auth_provider` columns. (c) `verify_demo.py` tampers with on-disk DB permanently. (d) Frontend: `signInWithGooglePrompt()` uses `prompt()` which blocks browser. (e) No `escapeHtml` function — XSS in all `innerHTML` calls. (f) Modal forms not reset on close. (g) No Escape key to close modals. |

### TIER 1 Fixes Needed:
1. Fix `test_api_flow.py` to use isolated test DB (override `get_db` dependency)
2. Update `conftest.py` schema to match `database.py` (add `phone`, `auth_provider`)
3. Set `booking_status = 'returned'` in the return endpoint
4. Append passport events for rejection and return actions
5. Add regression tests for each fix

---

## TIER 2: Robustness and Security (appropriate for a demo)

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 8 | Input validation on every endpoint (Pydantic): length limits, positive numbers, allowed categories, allowed enum values. | **FIX** | (a) `RentalCreate` has `ge=1, le=30` ✓. (b) `create_item` uses `Form(...)` NOT `ItemCreate` Pydantic model — **no validation on value/price/deposit** (can submit negative numbers). (c) `category` is never validated against `CATEGORIES` list. (d) `DisputeRequest.reason` and `ConfirmReturnRequest.condition_notes` have no `max_length`. |
| 9 | Consistent error format `{"detail": "..."}` with correct status codes. Frontend shows readable messages, never raw JSON or blank screen. | **FIX** | (a) Backend error format is consistent ✓ (`HTTPException(detail=...)`). (b) Frontend `apiFetch` extracts `data.detail` ✓. (c) But frontend shows errors via `showToast` which uses `innerHTML` with `err.message` — could show raw HTML. (d) Some error paths show `Failed to load items: ${err.message}` directly in `innerHTML`. |
| 10 | File upload safety: allow only jpg/png/webp, max 5 MB, check content type and extension, store with generated filename (never user's filename), serve from fixed folder. | **FIX** | (a) **No file size limit** — `await photo.read()` loads entire file into RAM. (b) **No MIME type check** — any file type accepted. (c) **No extension whitelist** — any extension is appended. (d) Filename uses `serial` which could contain path traversal characters. (e) Does use a generated filename (hash-based) ✓. |
| 11 | Prevent XSS: frontend must escape user-provided text before inserting into page; never use innerHTML with raw user data. | **MISSING** | **CRITICAL**: Zero escaping anywhere. No `escapeHtml()` function exists. All of the following are injected raw via `innerHTML`: `item.title`, `item.description`, `item.owner_name`, `rental.dispute_reason`, `rental.dispute_resolution`, `ev.actor_name`, `ev.details` (JSON in `<pre>`), `u.name`, `u.dorm`, `u.email`, `err.message`. 20+ injection points identified. |
| 12 | SQL safety: parameterized queries only. | **OK** | All SQL queries use `?` placeholders. No string interpolation in SQL. |
| 13 | Demo-only features clearly labelled and can be disabled with one `DEMO_MODE` config flag. | **MISSING** | (a) No `DEMO_MODE` flag in `config.py`. (b) `/api/demo/tamper` endpoint is always registered. (c) Hardcoded OTP `123456` cannot be disabled. (d) `X-User-Id` header auth has no toggle. (e) No `/api/demo/reset` endpoint. |
| 14 | No secrets, no hard-coded absolute paths; settings in `config.py`. `.gitignore` covers venv, `__pycache__`, `*.db`, uploads. | **FIX** | (a) `.gitignore` EXISTS and covers `__pycache__`, `*.pyc`, `.pytest_cache/`, `*.db`, `*.sqlite3`, `.env`, `uploads/` ✓. (b) But missing `venv/`, `.venv/`, `*.egg-info`. (c) `UPLOADS_DIR.mkdir()` runs at import time (side effect). (d) Hardcoded Unsplash avatar URL in `users.py`. |
| 15 | Database: indexes on foreign keys and frequent lookups, foreign keys enforced, one transaction per request with rollback on error. | **FIX** | (a) Indexes exist ✓ (`idx_items_category`, `idx_items_available`, `idx_passport_item`, `idx_rentals_item`, `idx_rentals_renter`, `idx_rentals_owner`). (b) Foreign keys enforced ✓. (c) `get_db()` uses `BEGIN IMMEDIATE` for every request including reads — **serializes all requests unnecessarily**. Read-only endpoints should not acquire write locks. |

### TIER 2 Fixes Needed:
1. Add `escapeHtml()` utility to `app.js` and apply everywhere
2. Add file upload validation (size, type, extension whitelist)
3. Add `DEMO_MODE` flag to `config.py`, guard demo endpoints
4. Add validation to `create_item` endpoint (category, positive values)
5. Fix `get_db()` to not use `BEGIN IMMEDIATE` for read endpoints (or accept the tradeoff for a demo)
6. Add `max_length` to text fields in schemas
7. Update `.gitignore` to cover `venv/`

---

## TIER 3: UX and Visual Design

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 16 | Consistent design system in CSS variables: colours, spacing, radius, shadows, typography. | **OK** | 29 CSS custom properties defined in `:root`. Used consistently across components. Dark mode palette is cohesive. |
| 17 | Header: branding, responsive, user auth area. | **OK** | Sticky glassmorphism header with brand, nav links, user chip button. Responsive at 768px. |
| 18 | Browse view: card grid, search, category pills, loading state, empty state. | **FIX** | (a) Card grid with auto-fill works ✓. (b) Search on Enter works ✓. (c) Category pills work ✓. (d) Loading state shown ✓. (e) Empty state shown ✓. (f) **No debounce on search** — only Enter key triggers. (g) **No pagination** — all items loaded at once. |
| 19 | Item detail / borrow modal: pricing, days selector, quote calculator. | **OK** | Borrow modal shows daily rate, total, deposit. Quote updates on day change. |
| 20 | Rental lifecycle cards: escrow stepper, contextual action buttons. | **FIX** | (a) Escrow FSM stepper displays correctly ✓. (b) Action buttons contextual by role and state ✓. (c) **Dispute reason shown unescaped** (XSS). (d) **No visual distinction between "accepted" and "returned" booking states** since return doesn't update booking_status. |
| 21 | Passport timeline: cryptographic verification banner, event blocks, tamper demo button. | **OK** | SHA-256 chain verified, banner shows valid/invalid, timeline renders blocks with hashes, tamper button works. |
| 22 | Reputation profile: renter and owner metric cards. | **OK** | Dual metric cards with color-coded values, "No history yet" for empty state. |
| 23 | About / What's Real page: fidelity table. | **OK** | Clean table with Built/Simulated/Vision badges. |
| 24 | Toast notifications: styled, positioned, auto-dismiss. | **FIX** | Works ✓ but message content is `innerHTML` (XSS risk). |
| 25 | Modals: frosted backdrop, close on backdrop click. | **FIX** | (a) Frosted backdrop ✓. (b) Close on backdrop click ✓. (c) **No Escape key close**. (d) **No focus trapping**. (e) **Forms not reset on close**. |
| 26 | Overall visual polish: consistent spacing, no jarring elements. | **FIX** | 40+ inline styles in `index.html` and pervasive inline styles in `app.js` template literals. Should be extracted to CSS classes. |

### TIER 3 Fixes Needed:
1. Extract inline styles to CSS classes
2. Add Escape key support for modals
3. Reset modal forms on close
4. Fix XSS in toasts and rental cards (covered by Tier 2 #11)

---

## TIER 4: Responsiveness and Accessibility

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 27 | Responsive at 768px and below. | **FIX** | One media query at `max-width: 768px` exists ✓. But no breakpoints for extra small (<380px) or large desktop (>1400px). |
| 28 | ARIA attributes on interactive elements. | **MISSING** | **Zero ARIA attributes** in the entire app. No `role="dialog"`, no `aria-modal`, no `aria-labelledby`, no `aria-live` on toasts, no `role="tab"`/`aria-selected` on tab buttons, no `aria-label="Close"` on close buttons. |
| 29 | WCAG AA contrast compliance. | **FIX** | `--text-muted` (#64748b) on `--bg-main` (#0b0f19) = ~3.9:1 contrast ratio. WCAG AA requires 4.5:1 for normal text. Need to lighten muted text color. |

### TIER 4 Fixes Needed:
1. Add ARIA attributes to modals, tabs, toasts, close buttons
2. Bump `--text-muted` to at least `#94a3b8` for AA compliance
3. Add `:focus-visible` styles to buttons and interactive elements

---

## TIER 5: Performance and Code Quality

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 30 | No N+1 queries; use JOINs. | **OK** | All list endpoints use JOINs to fetch related user/item names. |
| 31 | No unnecessary re-renders or duplicate API calls. | **FIX** | Each `loadBrowseItems()` / `loadMyRentals()` call replaces entire `innerHTML`, causing full DOM re-render. Acceptable for demo but noted. |
| 32 | Services must not import FastAPI. | **OK** | `passport.py`, `deposit.py`, `reputation.py`, `matching.py` — none import FastAPI. All are pure Python, testable independently. |
| 33 | Clean code: comments explain WHY not WHAT, no dead code. | **FIX** | (a) Comments are generally good ✓. (b) `app.js` line 1 says "RentAll" not "RENTX". (c) `conftest.py` has unused `from app.database import init_db`. (d) Hidden `<select id="user-select">` in HTML is dead code (was replaced by auth modal). |
| 34 | Consistent naming and formatting. | **OK** | Consistent snake_case in Python, camelCase in JS. Pydantic models follow clear naming. |

### TIER 5 Fixes Needed:
1. Fix "RentAll" → "RENTX" in app.js comment
2. Remove unused import in `conftest.py`
3. Remove or repurpose dead `<select id="user-select">`

---

## TIER 6: Testing

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 35 | All existing tests pass. | **FIX** | 17/18 pass. `test_api_flow.py::test_full_marketplace_lifecycle_flow` FAILS with 409 — test users have emails that conflict with seeded data because it runs against on-disk DB. |
| 36 | Test coverage: passport, deposit, reputation, matching, full API flow. | **FIX** | (a) Unit tests: passport (4), deposit (4), reputation (3), matching (4), auth (2) — good ✓. (b) API flow test: 1 E2E test covers happy path ✓. (c) **Missing tests**: dispute API flow, rejection flow, self-rent prevention, unavailable item rejection, double-booking prevention, file upload validation. (d) Integration tests run on on-disk DB — should use dependency override. |

### TIER 6 Fixes Needed:
1. Fix `test_api_flow.py` to use in-memory DB via dependency override
2. Fix `test_auth.py` to use in-memory DB via dependency override
3. Add test for dispute API flow
4. Add test for rejection flow
5. Add regression tests for bugs fixed in Tier 1

---

## TIER 7: Demo Readiness

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 37 | `seed.py` creates a compelling demo state. | **OK** | 6 users, 15 items with SVG placeholders, 4 rental histories (happy, late, disputed, active). Works correctly. |
| 38 | One-command launch: `pip install -r requirements.txt && python seed.py && uvicorn app.main:app --reload` | **OK** | Works. Requirements are minimal (fastapi, uvicorn, python-multipart). |
| 39 | Demo script / walkthrough documented. | **FIX** | (a) `README.md` has a 5-step demo script ✓. (b) `verify_demo.py` exists ✓. (c) But README says "16 tests" instead of 18. (d) README mixes "RENTX" and "RentAll" naming. (e) No `DEMO_SCRIPT.md` or `QA.md`. |
| 40 | `/api/demo/reset` endpoint to re-seed without restart. | **MISSING** | No reset endpoint exists. User must re-run `python seed.py` manually. |
| 41 | `/health` endpoint. | **MISSING** | No health check endpoint. |

### TIER 7 Fixes Needed:
1. Add `DEMO_MODE` flag and `/api/demo/reset` endpoint
2. Add `/health` endpoint
3. Fix README (test count, naming consistency)
4. Create `DEMO_SCRIPT.md` with presenter walkthrough

---

## TIER 8: Documentation and Honesty

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 42 | README: setup, architecture, what's real vs simulated, API reference. | **FIX** | (a) Setup guide ✓. (b) Architecture diagram ✓. (c) Fidelity matrix ✓. (d) **No API endpoint reference**. (e) Test count wrong (says 16, should be 18+). (f) Mixed naming. |
| 43 | "What's Real" page honestly labels demo features. | **OK** | About page has clear Built/Simulated/Vision categorization. |
| 44 | Code comments explain demo shortcuts honestly. | **FIX** | Most are good but some endpoints (like `/auth/google`) don't clearly comment that they're simulations. |

---

## Optional Stretch (if time permits)

| # | Requirement | Status | Evidence / Notes |
|---|-------------|--------|------------------|
| 45 | Image preview on item listing form. | **MISSING** | No preview shown before upload. |
| 46 | Search debounce (300ms). | **MISSING** | Search only triggers on Enter or button click. |
| 47 | Skeleton loading states. | **MISSING** | Loading text shown but no skeleton UI. |
| 48 | Dark/light theme toggle. | **MISSING** | Dark theme only, no toggle. |

---

## Implementation Order

After approval, I will implement in this order:

### Phase 1: TIER 1 (Correctness)
- Fix `return` endpoint to set `booking_status = 'returned'`
- Append passport events on rejection and return
- Fix `test_api_flow.py` to use isolated in-memory DB
- Sync `conftest.py` schema with `database.py`
- Add regression tests
- **Verify:** `pytest -v` all green + manual browser walkthrough of happy + dispute paths

### Phase 2: TIER 2 (Robustness & Security)
- Add `escapeHtml()` to `app.js`, apply everywhere
- Add file upload validation
- Add `DEMO_MODE` flag to config, guard demo endpoints
- Add server-side validation to `create_item`
- Add `max_length` to schemas
- Update `.gitignore`
- **Verify:** `pytest -v` + manual test of upload, validation errors, XSS attempts

### Phase 3: TIER 3 + 4 (UX + Accessibility)
- Extract inline styles to CSS classes
- Add Escape key / focus trapping to modals
- Add ARIA attributes
- Bump `--text-muted` for contrast
- Add `:focus-visible` styles
- **Verify:** Manual browser walkthrough, keyboard navigation test

### Phase 4: TIER 5 + 6 (Code Quality + Testing)
- Clean up dead code, fix comments/naming
- Add missing test cases (dispute flow, rejection, edge cases)
- **Verify:** `pytest -v` all green, full coverage report

### Phase 5: TIER 7 + 8 (Demo Readiness + Docs)
- Add `/health` and `/api/demo/reset` endpoints
- Fix and expand README
- Create `DEMO_SCRIPT.md`
- **Verify:** Full end-to-end demo walkthrough

### Phase 6: Optional Stretch (if time)
- Image preview, search debounce, skeleton loading

---

> **Files that will be changed per tier are listed in the phase descriptions above.**  
> **I will not delete or weaken any test to make it pass.**  
> **I will report: what changed, what I ran, anything still not working, after each tier.**

**⏳ Awaiting your approval to begin implementation.**
