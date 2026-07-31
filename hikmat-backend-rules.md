# Hikmat Backend — FastAPI Rules (Cursor / AI Agent Instructions)

You are working on the **Hikmat Wellness backend**: FastAPI + PostgreSQL (async SQLAlchemy)
+ Redis + Celery + Socket.IO (chat) + Firebase (push notifications), managed with `uv`,
fully Dockerized. Follow these rules on every change — apply them, don't restate them.

## Ground rules (non-negotiable)

1. **Never invent what you haven't verified.** Don't reference a library function,
   FastAPI/Pydantic/SQLAlchemy API, env var, config key, model field, or file path unless
   it's either (a) visible in the current codebase, or (b) certain to exist in the installed
   library version (check `pyproject.toml` / `uv.lock`). If unsure, say "I need to check X"
   and look — never guess and present it as fact.
2. **No redundant or speculative code.** Don't add abstraction layers, config options,
   feature flags, "just in case" parameters, or generic base classes nothing currently uses
   (YAGNI). If a future extension point is genuinely worth flagging, mention it in one line
   — don't pre-build it.
3. **Don't duplicate logic.** Before writing a new function/validator/query, check whether
   an equivalent already exists in `services/`, `repositories/`, or `utils/`. Extract shared
   logic instead of copy-pasting across domains/routers.
4. **Match the existing project structure.** New code goes in the layer it belongs to
   (route vs. service vs. repository), not wherever is quickest. Don't introduce a second
   ORM, a different validation style, or a parallel pattern without being asked.
5. **State assumptions explicitly.** If a requirement is ambiguous (required fields, status
   codes), pick the most sensible default, implement it, and say what you assumed in one
   line — don't silently guess, don't block on asking when a reasonable default exists.

## Layered architecture (always follow this flow)

```
Route (FastAPI router)  → request/response shaping only, no business logic
   Service               → business logic, orchestration, domain rules
      Repository         → data access only (SQLAlchemy queries), no business logic
         DB / Redis / Celery / External clients (Firebase, etc.)
```

- **Routes** stay thin: parse input (already validated by Pydantic), call one service
  method, return the response model. No `if`/business rules in routes.
- **Services** hold all business logic, are the only layer allowed to call multiple
  repositories or enforce domain rules (e.g. "user can't book two hakeems at the same time").
- **Repositories** only translate calls into queries — no decisions, no side effects beyond
  data access.
- Never let a route touch the DB/session directly. Never put SQL/ORM queries inside a
  service — that's the #1 layer-mixing violation to flag.

## Domain-driven structure

- Each domain (`auth`, `users`, `hakeem`, `booking`, `chat`, `community`, `forYou`,
  `notifications`) owns its own `models.py`, `schemas.py`, `repository.py`, `service.py`,
  `exceptions.py`.
- A domain's internals are not reached into directly by another domain — cross-domain
  interaction happens through that domain's service layer, not its repository.

## SOLID, applied concretely

- **S — Single Responsibility:** one service class per bounded domain (`AuthService`,
  `BookingService`), never one giant `UserService` doing auth + booking + notifications.
- **O — Open/Closed:** extend via new classes/strategy functions (e.g. a new
  `NotificationChannel` implementation) rather than editing a working function with a
  growing `if provider == "x"` chain.
- **L — Liskov Substitution:** if an interface/protocol is defined (`PushProvider`,
  `StorageBackend`), every implementation must be swappable without the caller changing.
- **I — Interface Segregation:** keep Pydantic schemas and service interfaces narrow —
  `UserCreateRequest` ≠ `UserResponse` ≠ `UserDBModel`. Don't force callers to depend on
  fields they don't use.
- **D — Dependency Inversion:** services depend on repository interfaces or receive them
  via `Depends()`, never instantiate a DB session or external client directly inside
  business logic. This is what makes unit testing possible without a live DB.

## DRY — concretely

- Shared query patterns (pagination, soft-delete filtering, "active user" checks) live once
  in `utils/` or a base repository — never re-implemented per domain.
- Shared response shapes (error envelope, paginated list wrapper) live once in
  `utils/response_envelope.py` — every endpoint reuses it.
- If the same validation rule appears in two schemas, extract a shared validator/mixin
  instead of pasting the same `@field_validator` twice.

## Pydantic & validation

- Always separate `RequestModel` / `ResponseModel` / ORM model — never return an ORM model
  directly from a route. Internal-only fields (password hashes, internal IDs) must not leak
  through a response schema by accident.
- Validation constraints (`min_length`, `ge`, custom validators) go in the Pydantic schema,
  not as manual `if` checks in the route.
- Use `pydantic-settings` for all config — never read `os.environ` ad hoc inside business code.

## Async & database

- Use `async def` consistently across routes/services with the async engine (`asyncpg`).
  Never mix blocking calls (`requests`, sync `psycopg2`) inside async code — use
  `httpx.AsyncClient` and async drivers.
- One DB session per request via `Depends(get_db_session)` — never share a session across
  requests or create ad hoc sessions inside a loop.
- Every query filtering "active" rows must respect the soft-delete convention
  (`WHERE deleted_at IS NULL`) if the table uses one.

## Error handling

- Services raise specific domain exceptions (`BookingConflictError`, `NotAuthorizedError`,
  `HakeemNotVerifiedError`) — never a bare `Exception` or raw `HTTPException` from inside a
  service. Mapping domain exceptions → HTTP status codes happens in one centralized
  exception handler, not scattered `try/except` blocks per route.
- Every error response follows one consistent envelope: `{error_code, message, details}` —
  never invent a new error shape per endpoint.

## Background jobs (Celery) & real-time (Socket.IO)

- Anything slow or non-critical-path (push notifications, booking reminders, community
  digest emails, recommendation precompute for `forYou`) goes through a Celery task — never
  inline in a request handler.
- Socket.IO handlers (`sockets/chat_handler.py`) stay thin like routes: validate, then
  delegate to the **same `ChatService`** used by the REST chat endpoints. Never duplicate
  business logic between a REST endpoint and a socket handler doing the same thing.
- Redis is the single source of truth for: Celery broker/result backend, Socket.IO session
  state (if scaling horizontally), and any short-lived cache. Don't add a second cache layer
  without reason.

## Firebase & notifications

- All Firebase Admin SDK calls are wrapped inside the `notifications` domain's service —
  no other domain imports `firebase_admin` directly. Other domains call
  `NotificationService.send(...)` and don't know or care that it's Firebase underneath
  (Dependency Inversion in practice).

## Before finishing any backend task — self-check

- [ ] Did I put logic in the right layer (route / service / repository)?
- [ ] Did I reuse an existing service/repository/schema instead of duplicating one?
- [ ] Did I verify every import/library call actually exists, rather than assuming?
- [ ] Did I avoid adding config/parameters/abstractions nothing currently needs?
- [ ] Are request/response/DB models properly separated?
- [ ] Is any slow/non-critical work offloaded to Celery instead of running inline?
- [ ] Did I state any assumption I made instead of silently guessing?