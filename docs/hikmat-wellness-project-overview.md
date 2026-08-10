# Hikmat Wellness — Project Overview

A complete picture of what this backend is, who it serves, how it is built, and what each module does — based on the current codebase under `Hikmat_BE` (not speculative future work).

| | |
|---|---|
| **Product name** | Hikmat Wellness |
| **API name** | Hikmat Wellness API (`APP_NAME`) |
| **Package** | `hikmat-be` |
| **Primary clients** | React Native mobile apps (patient + hakeem), ops/admin tools |
| **API base** | `/api/v1` |
| **Live docs** | `/docs` (OpenAPI / Swagger) when the API is running |

Related integration guides:

- [`docs/hakeem-integration.md`](./hakeem-integration.md) — Hakeem auth, dashboard, calendar, earnings, profile
- [`docs/chat-and-connections-integration.md`](./chat-and-connections-integration.md) — Messaging + connections
- [`docs/community-feed-integration.md`](./community-feed-integration.md) — Community feed
- [`hikmat-backend-rules.md`](../hikmat-backend-rules.md) — Engineering rules (layered architecture, SOLID, DRY)

---

## 1. What is Hikmat Wellness?

**Hikmat Wellness** is a digital health / wellness platform centered on **Unani (Hikmat) medicine**. It connects:

- People seeking traditional wellness guidance (**patients**)
- Verified Unani practitioners (**hakeems**)
- Platform operators who review practitioner credentials (**admins**)

The backend powers account creation, health/mizaj onboarding, practitioner discovery and verification, community content, real-time chat, connection requests, practitioner scheduling/availability, consultation bookings (data layer), and earnings/payout requests.

“Hikmat” refers to classical Greco-Arabic / Unani medical tradition; the product language in the UI and seeds reflects that (specializations like digestive health, herbal formulation, Hijama, etc.).

---

## 2. Who is it for?

### 2.1 Patients (default role: `patient`)

People using the consumer app to:

- Sign up and complete **onboarding** (profile, diet, activity, **mizaj** assessment, health interests, preferred language, preferred hakeem gender)
- Browse **verified hakeem** public profiles
- Join the **community** (posts, likes, comments, follows)
- **Connect** with practitioners / peers and **chat** in real time
- (Future-facing) book consultations — the `bookings` table and hakeem dashboard already assume patients; a dedicated patient booking REST API is not mounted yet

**Entry:** `POST /api/v1/auth/signup`

### 2.2 Hakeems / practitioners (role: `hakeem`)

Licensed or trained Unani practitioners who:

- Apply via a dedicated signup that creates a **verification application** (ID/license docs, experience, specializations, fee, bio)
- Wait for **admin approval** before appearing as verified in Discover / community badges
- Use a practitioner shell (documented against Figma): **Today**, **Calendar**, **Chat**, **Community**, **Profile / Earnings**
- Manage weekly + per-date **availability**, see today’s schedule and connection requests, request **payouts**

**Entry:** `POST /api/v1/auth/signup/hakeem` (not the patient signup)

### 2.3 Admins (role: `admin`)

Internal ops users who:

- Review hakeem applications (approve / reject / request more info)
- Are created via DB / seed (no public admin signup API)
- Will eventually confirm payouts manually (payout **request** is implemented; bank transfer is intentionally out of band)

**Example seed admin used in development:** `admin@hikmatwell.com` (when created via ops scripts)

---

## 3. High-level architecture

```
┌─────────────────────┐
│  React Native apps  │
│  (patient / hakeem) │
└──────────┬──────────┘
           │ REST  /api/v1
           │ Socket.IO  /socket.io/
           ▼
┌─────────────────────┐     ┌──────────────┐
│  FastAPI + Socket.IO│────►│  PostgreSQL  │
│  (ASGI: app.main)   │     │  (Supabase / │
└──────────┬──────────┘     │   Docker DB) │
           │                └──────────────┘
           ▼
┌─────────────────────┐
│  Redis              │  Socket.IO manager (scale-out);
│                     │  intended Celery broker (workers mostly stubbed)
└─────────────────────┘

Private verification docs → local disk and/or S3 (object storage util)
```

**Layering (enforced by project rules):**

```
Route  →  Service  →  Repository  →  DB / Redis / external clients
```

- Routes: thin, request/response only  
- Services: all business rules and cross-domain orchestration  
- Repositories: SQLAlchemy queries only  

Cross-domain calls go through **services**, not another domain’s repository (e.g. dashboard composes `BookingService` + `ConnectionsService` + `HakeemService`).

---

## 4. Technology stack

| Concern | Technology |
|---------|------------|
| Language | Python ≥ 3.12 |
| Package manager | `uv` |
| Web framework | FastAPI + Uvicorn |
| Real-time | python-socketio (ASGI-wrapped with FastAPI) |
| ORM / DB | SQLAlchemy 2 async + asyncpg → PostgreSQL |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt/passlib |
| Config | pydantic-settings |
| Cache / pub-sub | Redis |
| Jobs (planned) | Celery + Flower (compose present; task modules largely empty) |
| Push (planned) | `firebase-admin` dependency + config path; **not implemented in domain code yet** |
| File storage | Local private directory and/or AWS S3 (`boto3`) |
| Containers | Docker + docker-compose (`db`, `redis`, `api`, `celery_worker`, `flower`) |

**Run locally (typical):**

```bash
uv run python -m uvicorn app.main:app --reload
# or
docker compose up
```

---

## 5. User roles & auth at a glance

| Role | Value | How created | What they can access |
|------|--------|-------------|----------------------|
| Patient | `patient` | `POST /auth/signup` | Onboarding, community, chat, connections, public hakeem profiles |
| Hakeem | `hakeem` | `POST /auth/signup/hakeem` | All patient-capable social features + `/hakeem/*` practitioner APIs |
| Admin | `admin` | DB / seed | `/admin/hakeem-applications*` |

**Shared auth endpoints:** login, refresh, me (`Authorization: Bearer <access_token>`).

For hakeems, login / me responses include:

- `is_verified_hakeem` (boolean)
- `verification_status` (`pending` \| `under_review` \| `needs_more_info` \| `approved` \| `rejected`)

Gate “verified” UX with `is_verified_hakeem === true` or `verification_status === "approved"`.

---

## 6. Modules (domains) and purposes

Each domain typically owns: `models.py`, `schemas.py`, `repository.py`, `service.py`, `exceptions.py`.

### 6.1 Implemented & in use

| Module | Path | Purpose | Main capabilities |
|--------|------|---------|-------------------|
| **auth** | `app/domains/auth/` | Credentials & tokens | Signup (patient), login, refresh, JWT issue; no separate users-credentials table (password lives on `User`) |
| **users** | `app/domains/users/` | Accounts & onboarding | User profile fields, mizaj, diet, interests, soft-delete; `PATCH /users/me/onboarding`; enriches me/login with hakeem verification when role is hakeem |
| **lookups** | `app/domains/lookups/` | Controlled vocabularies | `GET /lookups` — health interests, post categories, flags, etc. used by onboarding and hakeem specializations |
| **hakeem** | `app/domains/hakeem/` | Practitioner lifecycle | Apply + profile; verification workflow; weekly/date availability; Today dashboard orchestration; self profile edit |
| **booking** | `app/domains/booking/` | Consultations | `Booking` model (patient ↔ hakeem, schedule, type, status, `can_join` window). Used by dashboard & calendar. **No public booking router mounted yet** |
| **payments** | `app/domains/payments/` | Earnings & payouts | `Transaction` + `PayoutBatch`; summary aggregations; payout history; request payout (≥ PKR 1,000 → admin queue). Exposed under `/hakeem/earnings/*` |
| **community** | `app/domains/community/` | Social feed | Posts, likes, comments, follows; feed tabs For You / Following / Trending; verified-hakeem badge derived from profile at read time |
| **chat** | `app/domains/chat/` | Messaging | Conversations, messages, reactions, delete for me/everyone; REST + Socket.IO share `ChatService` |
| **connections** | `app/domains/connections/` | Social graph | Friend-style requests (pending/accept/reject/cancel), blocks, relationship status; dashboard pending requests; response-rate stats |

### 6.2 Scaffold / not yet implemented

| Module | Path | Status |
|--------|------|--------|
| **forYou** | `app/domains/forYou/` | Empty stubs. The community feed’s **“For You” tab** is implemented inside **community**, not this package |
| **notifications** | `app/domains/notifications/` | Empty stubs. Firebase is a dependency/config placeholder only |
| **admin** (domain folder) | `app/domains/admin/` | Placeholder package; admin **HTTP** lives in `app/api/v1/endpoints/admin.py` and logic in `HakeemService` |

### 6.3 Supporting packages (not “domains” but important)

| Area | Path | Purpose |
|------|------|---------|
| API deps | `app/api/deps.py` | `get_current_user`, `require_admin`, `require_hakeem` |
| Sockets | `app/sockets/` | Socket.IO server + chat event handlers |
| Workers | `app/workers/` | Celery app + task files (currently empty / scaffold) |
| Utils | `app/utils/` | Cursor pagination, response helpers, private object storage |
| Core | `app/core/` | Settings, security (JWT/password), exception envelope |
| DB | `app/db/` | Async engine/session, Redis client, SQLAlchemy `Base` |
| Scripts | `app/scripts/` | Dev seeders for patients/community and verified hakeems |

---

## 7. Feature map by persona

### Patient journey

1. Sign up → JWT  
2. Complete onboarding (mizaj, interests, preferences)  
3. Load lookups for chips/forms  
4. Community feed + follow creators  
5. Discover verified hakeems (`GET /hakeems/{user_id}/profile`)  
6. Send connection request → accept opens chat conversation  
7. Message via REST and/or Socket.IO  

### Hakeem journey

1. Upload verification documents (multipart)  
2. `POST /auth/signup/hakeem` → pending application  
3. Admin approves → `is_verified_hakeem=true`  
4. **Today:** `GET /hakeem/dashboard` (schedule, stats, connection requests)  
5. **Calendar:** availability month view + weekly default + per-date PATCH  
6. **Chat / Community:** same modules as patients; posts show Verified badge  
7. **Profile:** `GET/PATCH /hakeem/me/profile`  
8. **Earnings:** summary, payout history, request payout  

### Admin journey

1. Login as `admin`  
2. List applications by status  
3. Open detail (signed document URLs)  
4. Approve / reject / request more info  

---

## 8. API surface (mounted routers)

All under **`/api/v1`** unless noted. Assembled in `app/api/v1/router.py`.

### Auth & identity

| Method | Path | Notes |
|--------|------|--------|
| POST | `/auth/signup` | Patient |
| POST | `/auth/signup/hakeem` | Hakeem application + account |
| POST | `/auth/login` | All roles |
| POST | `/auth/refresh` | Rotate tokens |
| GET | `/auth/me` | Current user (+ hakeem verification fields when applicable) |
| PATCH | `/users/me/onboarding` | Patient onboarding |
| GET | `/lookups` | Shared enums / chips |

### Community

| Method | Path |
|--------|------|
| POST | `/posts` |
| GET | `/posts/feed` |
| GET | `/posts/{post_id}` |
| POST/DELETE | `/posts/{post_id}/like` |
| POST/GET | `/posts/{post_id}/comments` |
| POST/DELETE | `/users/{user_id}/follow` |

### Chat

| Method | Path |
|--------|------|
| GET/POST | `/conversations` |
| GET/POST | `/conversations/{id}/messages` |
| PATCH | `/conversations/messages/{message_id}` |
| POST | `/conversations/messages/{message_id}/delete` |
| POST/DELETE | `/conversations/messages/{message_id}/reactions` |

### Connections

| Method | Path |
|--------|------|
| POST | `/connections/request` |
| GET | `/connections` |
| POST | `/connections/{id}/accept` \| `/reject` \| `/cancel` |
| POST/GET/DELETE | `/connections/block…` |
| GET | `/connections/relationship/{user_id}` |

### Hakeem public & practitioner

| Method | Path | Auth |
|--------|------|------|
| GET | `/hakeems/{user_id}/profile` | Public (verified only) |
| POST | `/uploads/verification-document` | Pre-signup upload |
| GET | `/hakeem/dashboard` | Hakeem |
| GET | `/hakeem/availability` | Hakeem |
| PUT | `/hakeem/availability/weekly-default` | Hakeem |
| PATCH | `/hakeem/availability/{day}` | Hakeem |
| GET/PATCH | `/hakeem/me/profile` | Hakeem |
| GET | `/hakeem/earnings/summary` | Hakeem |
| GET | `/hakeem/earnings/payout-history` | Hakeem |
| POST | `/hakeem/earnings/request-payout` | Hakeem |

### Admin

| Method | Path |
|--------|------|
| GET | `/admin/hakeem-applications` |
| GET | `/admin/hakeem-applications/{id}` |
| POST | `…/approve` \| `…/reject` \| `…/request-more-info` |

### Uploads

| Method | Path |
|--------|------|
| GET | `/uploads/signed` | Download private docs via short-lived signature |

### App health (no `/api/v1` prefix)

| Method | Path |
|--------|------|
| GET | `/` |
| GET | `/health` |

**Not mounted (files exist but empty / unused):** `endpoints/booking.py`, `endpoints/forYou.py`, `endpoints/notifications.py`.

---

## 9. Real-time chat (Socket.IO)

- Same host as the API; Engine.IO path `/socket.io/`
- Auth on connect: `auth: { token: accessToken }`
- Handlers stay thin and call **`ChatService`** (same as REST) — no duplicated message rules
- Redis adapter used when Redis is reachable; otherwise in-memory (single instance)

Typical events: `message:send`, `message:new`, edit/delete/reactions, typing, presence. Full contract: [`chat-and-connections-integration.md`](./chat-and-connections-integration.md).

---

## 10. Data model (tables)

Created via Alembic migrations under `alembic/versions/`.

| Area | Tables |
|------|--------|
| Identity | `users`, `lookup_options` |
| Hakeem | `hakeem_profiles`, `hakeem_weekly_availability`, `hakeem_date_availability` |
| Booking / money | `bookings`, `transactions`, `payout_batches` |
| Community | `posts`, `post_likes`, `post_comments`, `follows` |
| Chat | `conversations`, `conversation_participants`, `messages`, `message_reactions`, `message_hidden_for_users` |
| Graph | `connections`, `blocks` |

No tables yet for the stub `forYou` or `notifications` domains.

---

## 11. Background jobs & notifications (current reality)

| Planned | Current state |
|---------|----------------|
| Celery tasks (booking reminders, digests, pushes) | `app/workers/*.py` mostly empty; compose still defines worker + Flower |
| Firebase push via `NotificationService` | Domain folder stubbed; **no** `firebase_admin` usage in app code yet |
| Rules intent | Slow / non-critical work should go through Celery; only `notifications` domain talks to Firebase |

Treat push and Celery as **architecture reserved**, not product-ready features, until those modules are filled in.

---

## 12. Dev seeding & testing helpers

| Script | Command | Purpose |
|--------|---------|---------|
| Patient / social seed | `uv run python -m app.scripts.seed_test_data` [`--reset`] | Test users, community, chat, connections |
| Verified hakeems | `uv run python -m app.scripts.seed_verified_hakeems` [`--reset`] | 5 approved hakeems (`is_verified_hakeem=true`) |

Common seed password: **`Test@1234`**.

Example verified hakeem emails: `hakeem.rehman@yopmail.com`, `hakeem.yusuf@yopmail.com`, …

---

## 13. Repository layout (mental map)

```
Hikmat_BE/
├── app/
│   ├── main.py              # FastAPI + Socket.IO ASGI entry (`app`)
│   ├── api/v1/              # HTTP routers
│   ├── domains/             # Business domains (see §6)
│   ├── sockets/             # Socket.IO
│   ├── workers/             # Celery (scaffold)
│   ├── core/                # config, security, exceptions
│   ├── db/                  # session, redis, Base
│   ├── utils/               # pagination, storage, envelopes
│   └── scripts/             # seeders
├── alembic/                 # migrations
├── docs/                    # frontend integration + this overview
├── docker-compose.yml
├── Dockerfile
├── hikmat-backend-rules.md
└── pyproject.toml
```

---

## 14. Product principles reflected in the backend

1. **Verification before trust** — public hakeem profiles and “Verified Hakeem” badges only after admin approval; badge is always derived live from `HakeemProfile`, not denormalized onto posts.  
2. **Practitioner ops in one shell** — Today / Calendar / Chat / Community / Profile map cleanly onto dashboard, availability, chat, community, profile+earnings APIs.  
3. **Compose, don’t duplicate** — dashboard orchestrates booking + connections + hakeem services; chat REST and sockets share one service.  
4. **Money is staged** — earnings aggregations and payout *requests* exist; actual bank transfer remains an admin/manual step.  
5. **YANGI with reserved slots** — `forYou`, `notifications`, and Celery task files exist as placeholders so the structure matches the long-term product plan without fake implementations.

---

## 15. Known gaps (honest inventory)

Use this when planning frontend or next backend sprints:

| Gap | Detail |
|-----|--------|
| Patient booking API | Bookings power hakeem Today/Calendar; no mounted patient “create booking” router yet |
| Notifications / FCM | Dependency + empty domain only |
| Celery business tasks | Compose wires workers; task bodies empty |
| Admin payout console | Hakeems can request payout; no dedicated admin payout approve/pay endpoints listed |
| Discover list API | Public profile-by-id exists; a curated “list all verified hakeems” endpoint is not a separate mounted resource in the router (clients may use seeds / other lists) |
| Root README | This overview + domain guides fill that role |

---

## 16. Quick “what should I read next?”

| If you are… | Read |
|-------------|------|
| Building the **hakeem** RN app | `docs/hakeem-integration.md` |
| Building **chat / connections** | `docs/chat-and-connections-integration.md` |
| Building the **community** feed | `docs/community-feed-integration.md` |
| Extending the **backend** | `hikmat-backend-rules.md` + this file §6–§8 |
| Exploring live contracts | Run API → open `/docs` |

---

*Generated from the Hikmat_BE codebase as of the project’s current implementation. Prefer OpenAPI (`/docs`) and the domain integration guides when wiring a specific screen.*
