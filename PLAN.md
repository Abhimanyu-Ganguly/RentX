# Implementation Plan: "Buy Nothing, Rent Everything" (RentAll)

A campus-first equipment borrowing marketplace with verifiable item passports, simulated escrow deposit state machine, multidimensional reputation scoring, and need-based bundling.

## Folder Tree
```
rentall/
  app/
    __init__.py
    config.py          # App name, DB path, categories, checklist templates, needs config
    database.py        # SQLite schema initialization, transaction-per-request dependency
    schemas.py         # Pydantic v2 schemas for all requests/responses
    routers/
      __init__.py
      users.py         # User listing, creation, switch user, reputation
      items.py         # Item creation (with photo/hash), item listing/filtering, passport inspection
      rentals.py       # Rental lifecycle: request, accept/reject, return, confirm return, dispute, resolve
      matching.py      # Need-based bundle generator
      demo.py          # Demo tampering & reset endpoints (demo-only)
    services/
      __init__.py
      passport.py      # SHA-256 item hashing, append-only hash-chain verification & appending
      deposit.py       # Pure Python state machine with strict transition matrix & error handling
      reputation.py    # On-demand metrics computation (renter punctuality/care, owner reliability/response time)
      matching.py      # NLP-ready keyword extraction & bundle search with inventory resolution
  static/
    index.html         # Single Page App shell with navigation, toast container, hash-routed views
    styles.css         # Modern clean design tokens, status badges, timeline styling, responsive layout
    app.js             # Vanilla JS state management, API client (X-User-Id), dynamic rendering, hash router
  tests/
    __init__.py
    conftest.py        # Pytest fixtures for in-memory / temporary test database & TestClient
    test_passport.py   # Hash-chain integrity, tamper detection, multi-item independence
    test_deposit.py    # Transition matrix validation (all legal & illegal paths)
    test_reputation.py # Hand-calculated math verification & edge cases (zero division safety)
    test_matching.py   # Bundling logic, inventory lookup, partial/full availability
    test_api_flow.py   # Full integration flow: Register -> List -> Request -> Accept -> Return -> Confirm -> Passport Check
  seed.py              # Seeds 6 users, 15 items, multi-state rental histories via service layer
  requirements.txt     # Pinned dependencies
  README.md            # Architecture, setup, demo script, feature fidelity matrix
  PLAN.md              # Milestone tracking & architectural blueprint
```

## Milestones & Execution Plan

### Milestone 1: Project Setup, Config, Database, and Dependencies
- Set up `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `python-multipart`, `pytest`, `httpx`).
- Implement `app/config.py` with configurable `APP_NAME`, categories, condition templates, and need mappings.
- Implement `app/database.py` with SQLite table schema definitions, WAL mode, foreign key enforcement, and FastAPI transactional request dependency (`BEGIN IMMEDIATE`).
- Implement `app/schemas.py` with Pydantic v2 validation models.

### Milestone 2: Core Domain Services & Unit Tests
- `services/passport.py`: SHA-256 item hashing, append-only hash chain construction, verify function returning `(is_valid, broken_at_seq)`.
- `services/deposit.py`: Explicit deposit transition state machine (`pending` -> `held` -> `released`, `held` -> `disputed` -> `resolved`), smart-contract mapping documentation.
- `services/reputation.py`: Renter (punctuality %, care %, disputes, success count) and Owner (reliability %, response hours, disputes) on-demand computation.
- `services/matching.py`: Need matching dictionary, text normalization, item search, bundle compilation with missing tag reporting.
- Write unit tests (`test_passport.py`, `test_deposit.py`, `test_reputation.py`, `test_matching.py`) and run `pytest`.

### Milestone 3: API Routers & Integration Flow Test
- Implement routers: `users.py`, `items.py`, `rentals.py`, `matching.py`, `demo.py`.
- Wire routers into `app/main.py` with static file mounting at `/static` and root redirect.
- Write and run `tests/test_api_flow.py` with `fastapi.testclient.TestClient`.

### Milestone 4: Seed Data Script
- Implement `seed.py` that populates 6 distinct campus personas, 15 realistic items across 5 categories with generated placeholder images, and realistic rental history (including late return & dispute) calling service functions to preserve cryptographic hash chain integrity.

### Milestone 5: Frontend SPA (HTML/CSS/JS)
- Build responsive single-page application in `static/`:
  - Top navigation with demo user switcher, current user balance/profile snippet, app title.
  - View 1: Browse & Filter (category pills, search, price/deposit badges, owner rep badge, rent action modal).
  - View 2: Need Search (big prompt, interactive bundle cards, single-click rent bundle).
  - View 3: List an Item (category condition checklist generator, photo upload, generated SHA-256 preview).
  - View 4: My Rentals (Renter & Owner tabs, deposit timeline, lifecycle action buttons: accept/reject, return, confirm return with 1-5 stars rating, dispute/resolve).
  - View 5: Item Passport (verifiable hash timeline, validity verification badge, demo tamper button).
  - View 6: User Profile & Reputation (Renter & Owner breakdowns, dispute history).
  - View 7: About / What's Real (Built vs Simulated vs Vision breakdown).
  - Toast notification system, clean modal dialogs, empty states.

### Milestone 6: Verification, 5-Step Demo Walkthrough & README.md
- Run full pytest test suite.
- Run `seed.py` and start the server.
- Walk through the 5-step demo via automated test and curl/script verification.
- Write complete `README.md` with problem, solution, Mermaid architecture diagram, 3-command setup, demo script, and design decisions.
