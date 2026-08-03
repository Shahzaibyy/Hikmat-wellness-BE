# Hakeem — Frontend Integration Guide (React Native)

Complete guide for integrating **Hakeem (practitioner) auth, verification, dashboard, calendar, earnings, profile, and related screens** against the Hikmat backend.

Base URL: `/api/v1`  
Auth header (all protected routes): `Authorization: Bearer <access_token>`

OpenAPI live docs: `GET /docs` (after `uv run python -m uvicorn app.main:app --reload`)

---

## Table of contents

1. [Auth model & roles](#1-auth-model--roles)
2. [Hakeem signup / verification application flow](#2-hakeem-signup--verification-application-flow)
3. [Login, refresh, me](#3-login-refresh-me)
4. [Public hakeem profile (patient / discover)](#4-public-hakeem-profile-patient--discover)
5. [Today dashboard](#5-today-dashboard)
6. [Calendar & availability](#6-calendar--availability)
7. [Earnings & payouts](#7-earnings--payouts)
8. [Self profile (Profile tab)](#8-self-profile-profile-tab)
9. [Connection requests on dashboard](#9-connection-requests-on-dashboard)
10. [Messages / Community / navigation mapping](#10-messages--community--navigation-mapping)
11. [Admin verification (ops / admin app)](#11-admin-verification-ops--admin-app)
12. [Error envelope & codes](#12-error-envelope--codes)
13. [Lookups used by hakeem forms](#13-lookups-used-by-hakeem-forms)
14. [Suggested RN screen → API map](#14-suggested-rn-screen--api-map)
15. [Test accounts & curl cheatsheet](#15-test-accounts--curl-cheatsheet)

---

## 1. Auth model & roles

| Role | `user.role` value | Notes |
|------|-------------------|--------|
| Patient | `patient` | Default; use `POST /auth/signup` |
| Hakeem | `hakeem` | Created only via `POST /auth/signup/hakeem` |
| Admin | `admin` | Set in DB / seed; gates `/admin/*` |

Practitioner-only routes under `/hakeem/*` require:

- Valid Bearer access token
- `user.role === "hakeem"` (`require_hakeem`)

If a patient token hits `/hakeem/*` → **403** `FORBIDDEN`.

Verification badges in the UI come from `HakeemProfile.is_verified_hakeem` (set only when an admin **approves** the application). A hakeem can log in before approval, but public Discover profile returns 404 until verified.

### Token response (all auth endpoints)

```ts
type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  user: UserResponse;
};

type UserResponse = {
  id: string; // UUID
  email: string;
  full_name: string | null;
  role: "patient" | "hakeem" | "admin";
  avatar_url: string | null;
  city: string | null;
  // …onboarding fields (patients mainly)
  onboarding_completed: boolean;
  // …
};
```

Store `access_token` + `refresh_token` securely (e.g. `expo-secure-store`). Attach access token on every authenticated request. On 401, call refresh then retry.

---

## 2. Hakeem signup / verification application flow

### Recommended RN wizard steps

```
1. Account   → email, password, full_name
2. Documents → upload national ID + license files
3. Practice  → specializations, years, city, languages, fee, bio
4. Screening → institute, reason for joining, optional refs
5. Terms     → agrees_to_terms must be true
6. Submit    → POST /auth/signup/hakeem  (single API call)
7. Pending   → show “Under review” until admin approves
```

Signup **creates the user + hakeem profile + pending application in one request**. Do **not** call patient `POST /auth/signup` for practitioners.

### Step A — Upload verification documents (before submit)

`POST /api/v1/uploads/verification-document`  
Auth: **none** (needed before account exists)  
Content-Type: `multipart/form-data`

| Form field | Type | Required | Notes |
|------------|------|----------|--------|
| `document_type` | string | yes | `national_id` or `license` |
| `file` | file | yes | JPEG, PNG, or PDF; max **8 MiB** |

**Response `200`:**

```ts
{
  document_url: string; // private storage URL — send this in signup JSON
  document_type: "national_id" | "license";
  key: string;
}
```

**RN tip (FormData):**

```ts
const form = new FormData();
form.append("document_type", "national_id");
form.append("file", {
  uri: asset.uri,
  name: asset.fileName ?? "id.jpg",
  type: asset.mimeType ?? "image/jpeg",
} as any);

const res = await fetch(`${API}/api/v1/uploads/verification-document`, {
  method: "POST",
  body: form,
  // do NOT set Content-Type manually — let fetch set the boundary
});
```

Upload twice (ID + license). Keep both `document_url` values for the signup body.

### Step B — Submit application

`POST /api/v1/auth/signup/hakeem`  
Auth: none  
Content-Type: `application/json`

**Request body:**

```ts
{
  email: string;                    // valid email
  password: string;                 // min 8 chars
  full_name: string;                // 1–120

  national_id_number: string;       // 5–64
  national_id_document_url: string; // from upload step
  license_number?: string | null;
  license_document_url: string;     // from upload step

  specializations: string[];        // lookup keys type=health_interest, min 1
  years_of_experience: number;      // 1–60; **service enforces ≥ 2**
  city: string;                     // 1–120
  languages_spoken: string[];       // "urdu" | "english" | "punjabi"
  consultation_fee: number;         // > 0 (PKR)
  bio: string;                      // 20–1000 chars

  training_institute: string;       // 1–200
  previous_practice_location?: string | null;
  reason_for_joining: string;       // 20–1000
  reference_contact?: string | null;
  agrees_to_terms: true;            // must be true
}
```

**Response `200`:** `TokenResponse` (same as login). User has `role: "hakeem"`.  
Profile starts with:

- `verification_status`: `"pending"`
- `is_verified_hakeem`: `false`

**Common errors:**

| Status | `error_code` | When |
|--------|--------------|------|
| 409 | `USER_ALREADY_EXISTS` | Email taken (patient or other) |
| 409 | `HAKEEM_ALREADY_APPLIED` | Hakeem profile already exists for that email |
| 422 | `INVALID_HAKEEM_APPLICATION` | Bad specialization/language, `< 2` years experience, etc. Check `details.field` |

After signup, route the user to a **pending verification** screen. Poll `GET /hakeem/me/profile` (or re-login and check `is_verified_hakeem`) until approved — or wait for a future push notification.

---

## 3. Login, refresh, me

Hakeems use the **same** auth endpoints as patients after signup.

### `POST /api/v1/auth/login`

```json
{ "email": "hakeem.rehman@yopmail.com", "password": "Test@1234" }
```

→ `TokenResponse`. Gate the app shell with `user.role === "hakeem"`.

### `POST /api/v1/auth/refresh`

```json
{ "refresh_token": "<refresh_token>" }
```

→ fresh `TokenResponse`.

### `GET /api/v1/auth/me`

Auth: Bearer  
→ `UserResponse` (includes `role`).

---

## 4. Public hakeem profile (patient / discover)

### `GET /api/v1/hakeems/{user_id}/profile`

Auth: optional/none (public)  
Only returns **verified** hakeems.

**Response `200`:**

```ts
{
  id: string;              // profile UUID
  user_id: string;
  full_name: string | null;
  avatar_url: string | null;
  specializations: string[] | null;
  bio: string | null;
  city: string | null;
  years_of_experience: number | null;
  languages_spoken: string[] | null;
  consultation_fee: number | null;
  rating_avg: number | null;
  rating_count: number;
  is_verified_hakeem: true;
}
```

**404** `HAKEEM_NOT_VERIFIED` — not found or not yet approved (do not leak pending applications).

---

## 5. Today dashboard

Maps to the **Today** tab in the practitioner app.

### `GET /api/v1/hakeem/dashboard`

Auth: Bearer + role `hakeem`

**Response `200`:**

```ts
{
  greeting_name: string | null;
  consultations_today_count: number;
  quick_stats: {
    consultations_this_week: number;
    average_rating: number | null;   // from HakeemProfile.rating_avg
    response_rate: number;           // % of connection requests answered within 24h
  };
  todays_schedule: Array<{
    id: string;
    patient_id: string;
    patient_name: string | null;
    patient_avatar_url: string | null;
    scheduled_at: string;            // ISO-8601 — format in local TZ for UI
    appointment_type: string;        // e.g. "Follow-up", "Initial Consultation"
    can_join: boolean;               // true only in join window (15 min before start → end)
    status: string;                  // pending | confirmed | cancelled | completed | no_show
  }>;
  pending_connection_requests: Array<{
    id: string;                      // connection id — use for accept/reject
    requester_id: string;
    requester_name: string | null;
    requester_avatar_url: string | null;
    note: string | null;             // currently always null (no note field yet)
    created_at: string;              // ISO
  }>;
}
```

**UI wiring:**

| UI element | Field |
|------------|--------|
| “Good morning, Dr. …” | `greeting_name` |
| “You have N consultations today” | `consultations_today_count` |
| Stats cards | `quick_stats.*` |
| Schedule list + Msg / Join | `todays_schedule` — enable **Join** only when `can_join === true` |
| Connection request Accept / Decline | `pending_connection_requests` → call connections accept/reject |

**Accept / Decline (reuse connections domain):**

```http
POST /api/v1/connections/{connection_id}/accept
POST /api/v1/connections/{connection_id}/reject
Authorization: Bearer …
```

**Msg** → open chat via existing conversations API (see `docs/chat-and-connections-integration.md`).

---

## 6. Calendar & availability

Maps to the **Calendar** tab.

### Model (important for FE)

Backend supports **both**:

1. **Weekly default** — recurring Mon–Sun pattern  
2. **Per-date override** — tap a day → bottom sheet → set available/unavailable + slots  

Calendar month dots:

| Dot | Meaning | Field |
|-----|---------|--------|
| Green | Has availability (weekly or override) | `has_availability` |
| Orange | Has confirmed/pending appointment | `has_appointment` |
| Both | Both true | render both dots |

### `GET /api/v1/hakeem/availability?month=&year=`

Auth: Bearer + hakeem  

Query:

| Param | Type | Required |
|-------|------|----------|
| `month` | int 1–12 | yes |
| `year` | int 2020–2100 | yes |

**Response `200`:**

```ts
{
  year: number;
  month: number;
  days: Array<{
    date: string;              // "YYYY-MM-DD"
    has_availability: boolean;
    has_appointment: boolean;
  }>;
  upcoming: Array<{
    id: string;
    hakeem_user_id: string;
    patient: { id, full_name, avatar_url };
    scheduled_at: string;      // ISO datetime
    duration_minutes: number;
    appointment_type: string;
    status: string;            // map to Confirmed / Pending badges
    can_join: boolean;
  }>;
}
```

**Status badges (suggested):**

- `confirmed` → green “Confirmed”
- `pending` → orange “Pending”

### `PUT /api/v1/hakeem/availability/weekly-default`

Set (replace) the recurring weekly pattern. Auth: hakeem.

**Request:**

```ts
{
  days: Array<{
    day_of_week: number;       // 0=Monday … 6=Sunday
    is_available: boolean;
    slots: Array<{             // required if is_available=true
      start_time: string;      // "HH:MM:SS" or "HH:MM"
      end_time: string;
    }>;
  }>;
}
```

Example — Mon–Fri 09:00–17:00:

```json
{
  "days": [
    { "day_of_week": 0, "is_available": true, "slots": [{ "start_time": "09:00:00", "end_time": "17:00:00" }] },
    { "day_of_week": 1, "is_available": true, "slots": [{ "start_time": "09:00:00", "end_time": "17:00:00" }] },
    { "day_of_week": 2, "is_available": true, "slots": [{ "start_time": "09:00:00", "end_time": "17:00:00" }] },
    { "day_of_week": 3, "is_available": true, "slots": [{ "start_time": "09:00:00", "end_time": "17:00:00" }] },
    { "day_of_week": 4, "is_available": true, "slots": [{ "start_time": "09:00:00", "end_time": "17:00:00" }] },
    { "day_of_week": 5, "is_available": false, "slots": [] },
    { "day_of_week": 6, "is_available": false, "slots": [] }
  ]
}
```

**Response:** list of saved weekly slots:

```ts
Array<{ day_of_week: number; start_time: string; end_time: string; is_available: boolean }>
```

### `PATCH /api/v1/hakeem/availability/{day}`

Quick per-date toggle (`day` = `YYYY-MM-DD`). Auth: hakeem.

**Request — mark available with slots:**

```json
{
  "is_available": true,
  "slots": [
    { "start_time": "09:00:00", "end_time": "12:00:00" },
    { "start_time": "14:00:00", "end_time": "17:00:00" }
  ]
}
```

**Request — mark whole day unavailable:**

```json
{ "is_available": false, "slots": [] }
```

**Response:**

```ts
{
  date: string;
  is_available: boolean;
  slots: Array<{ date, start_time, end_time, is_available }>;
}
```

**Conflict `409` `AVAILABILITY_CONFLICT`:**

- Cannot mark a day unavailable if a **confirmed** booking exists that day
- Cannot set available slots that fail to cover an existing confirmed booking window

Show the `message` from the error envelope in a toast / alert.

---

## 7. Earnings & payouts

Maps to Profile → Earnings section / expandable earnings UI.

Currency is **PKR**. Amounts are decimals (JSON numbers/strings — treat as money strings in RN if needed).

### `GET /api/v1/hakeem/earnings/summary`

Auth: hakeem

```ts
{
  pending_balance: string | number;     // e.g. 18500.00
  currency: "PKR";
  available_withdrawal_date: string | null; // ISO — “Available for withdrawal …”
  this_month: string | number;
  last_month: string | number;
  total_earned: string | number;
}
```

| UI | Field |
|----|--------|
| Pending balance card | `pending_balance` + `currency` |
| “Available for withdrawal …” | format `available_withdrawal_date` |
| This month / Last month / Total | `this_month`, `last_month`, `total_earned` |

### `GET /api/v1/hakeem/earnings/payout-history?cursor=&limit=`

Auth: hakeem  
Cursor pagination (`limit` default 20, max 50).

```ts
{
  items: Array<{
    id: string;
    amount: string | number;
    currency: string;
    status: "pending_review" | "approved" | "paid" | "rejected";
    reference: string;           // e.g. "PAY-2938…"
    requested_at: string;
    paid_at: string | null;
  }>;
  next_cursor: string | null;
  has_more: boolean;
}
```

Suggested badge: `paid` → “Paid”.

### `POST /api/v1/hakeem/earnings/request-payout`

Auth: hakeem  
No body. Creates / queues a payout for **admin review** (does **not** transfer money).

**Rules:**

- Minimum pending balance: **PKR 1,000**
- Only one open `pending_review` payout at a time

**Response `200`:**

```ts
{
  id: string;
  amount: string | number;
  currency: "PKR";
  status: "pending_review";
  reference: string;
  requested_at: string;
  message: string;
}
```

**Errors:**

| Status | `error_code` |
|--------|--------------|
| 400 | `INSUFFICIENT_PAYOUT_BALANCE` |
| 409 | `PAYOUT_ALREADY_PENDING` |

Disable the **Request Payout** button when `pending_balance < 1000` or a pending payout already exists.

---

## 8. Self profile (Profile tab)

### `GET /api/v1/hakeem/me/profile`

Auth: hakeem

```ts
{
  id: string;
  user_id: string;
  full_name: string | null;
  avatar_url: string | null;
  email: string | null;
  specializations: string[] | null;
  bio: string | null;
  city: string | null;
  years_of_experience: number | null;
  languages_spoken: string[] | null;
  consultation_fee: number | null;
  rating_avg: number | null;
  rating_count: number;
  is_verified_hakeem: boolean;      // orange check badge on avatar
  verification_status: string;      // pending | under_review | needs_more_info | approved | rejected
  patients_count: number;           // accepted connections count
}
```

| UI | Field |
|----|--------|
| Name | `full_name` |
| “Unani · City” | join specializations / city as you prefer |
| Years / Rating / Patients | `years_of_experience`, `rating_avg`, `patients_count` |
| Specialization pills | `specializations` |
| About | `bio` |
| Verified badge | `is_verified_hakeem` |

### `PATCH /api/v1/hakeem/me/profile`

Auth: hakeem  
Partial update — send only fields that changed.

```ts
{
  bio?: string;                 // 20–1000
  specializations?: string[];   // health_interest lookup keys
  consultation_fee?: number;    // > 0
  languages_spoken?: string[];  // urdu | english | punjabi
  city?: string;                // 1–120
}
```

**Response:** same shape as GET.

**Policy:** editing these fields does **not** reset verification. Identity documents and years of experience are not editable here.

Invalid specialization/language → `422` `INVALID_HAKEEM_APPLICATION` with `details.field`.

---

## 9. Connection requests on dashboard

Accept / reject use the shared connections API (not under `/hakeem`).

| Action | Method | Path |
|--------|--------|------|
| Accept | `POST` | `/api/v1/connections/{id}/accept` |
| Reject | `POST` | `/api/v1/connections/{id}/reject` |
| List (optional) | `GET` | `/api/v1/connections?status=pending` |

Accept returns `ConnectionResponse` including `conversation_id` when chat is created — navigate to Messages with that id.

Full details: [`docs/chat-and-connections-integration.md`](./chat-and-connections-integration.md).

---

## 10. Messages / Community / navigation mapping

Bottom nav (practitioner app):

| Tab | Backend |
|-----|---------|
| Today | `GET /hakeem/dashboard` |
| Calendar | `GET /hakeem/availability` + availability PATCH/PUT |
| Chat | Existing `/conversations` + Socket.IO |
| Community | Existing `/posts/*` — author `is_verified_hakeem` is derived live from profile |
| Profile | `GET/PATCH /hakeem/me/profile` + earnings endpoints |

### Community — Verified Hakeem badge

On feed/post/comment responses, `author.is_verified_hakeem` is computed at **read time** from `HakeemProfile.is_verified_hakeem`.  
Do **not** cache a local “verified” flag on the post — if verification changes, the next feed fetch reflects it.

See [`docs/community-feed-integration.md`](./community-feed-integration.md).

---

## 11. Admin verification (ops / admin app)

All require Bearer + `role === "admin"`.

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/admin/hakeem-applications?status=&cursor=&limit=` | Cursor page of applications |
| `GET` | `/admin/hakeem-applications/{application_id}` | Detail + **signed** document URLs |
| `POST` | `/admin/hakeem-applications/{application_id}/approve` | Sets `is_verified_hakeem=true` |
| `POST` | `/admin/hakeem-applications/{application_id}/reject` | Body: `{ "notes"?: string }` |
| `POST` | `/admin/hakeem-applications/{application_id}/request-more-info` | Body: `{ "notes": string }` **required** |

`status` query enum: `pending` \| `under_review` \| `needs_more_info` \| `approved` \| `rejected` (default `pending`).

Admin detail response includes sensitive fields (`national_id_number`, document URLs, screening answers). Never reuse this schema on the patient app.

---

## 12. Error envelope & codes

All domain errors:

```ts
{
  error_code: string;
  message: string;
  details: Record<string, unknown> | null;
}
```

| `error_code` | Typical status | Meaning |
|--------------|----------------|---------|
| `FORBIDDEN` | 403 | Not hakeem / not admin |
| `INVALID_TOKEN` | 401 | Missing/expired Bearer |
| `HAKEEM_ALREADY_APPLIED` | 409 | Duplicate application |
| `HAKEEM_NOT_VERIFIED` | 404 | Public profile unavailable |
| `HAKEEM_NOT_FOUND` | 404 | No profile for this user |
| `INVALID_HAKEEM_APPLICATION` | 422 | Validation (field in `details`) |
| `AVAILABILITY_CONFLICT` | 409 | Booking vs availability clash |
| `INSUFFICIENT_PAYOUT_BALANCE` | 400 | Below PKR 1000 |
| `PAYOUT_ALREADY_PENDING` | 409 | Open payout exists |
| `USER_ALREADY_EXISTS` | 409 | Email taken |

FastAPI validation errors (wrong types / missing fields) may return the default `{ "detail": [...] }` shape — handle both.

---

## 13. Lookups used by hakeem forms

`GET /api/v1/lookups`

| Form field | Lookup / enum |
|------------|----------------|
| `specializations` | `health_interest` keys from lookups |
| `languages_spoken` | Fixed: `urdu`, `english`, `punjabi` |

Load lookups once at app start; use chips/multi-select bound to keys (send keys, display labels).

---

## 14. Suggested RN screen → API map

| Screen | Primary calls |
|--------|----------------|
| Hakeem signup wizard | upload ×2 → `POST /auth/signup/hakeem` |
| Pending verification | `GET /hakeem/me/profile` (watch `verification_status`) |
| Login | `POST /auth/login` |
| Today | `GET /hakeem/dashboard` + connections accept/reject |
| Calendar month | `GET /hakeem/availability?month&year` |
| Availability settings (weekly) | `PUT /hakeem/availability/weekly-default` |
| Date bottom sheet | `PATCH /hakeem/availability/{YYYY-MM-DD}` |
| Messages | `/conversations` + Socket.IO |
| Community | `/posts/feed` (show verified badge from author) |
| Profile header | `GET /hakeem/me/profile` |
| Edit profile | `PATCH /hakeem/me/profile` |
| Earnings | `GET /hakeem/earnings/summary` + payout-history + request-payout |
| Patient Discover card | `GET /hakeems/{user_id}/profile` |

### Auth header helper

```ts
headers: {
  Authorization: `Bearer ${accessToken}`,
  Accept: "application/json",
  "Content-Type": "application/json",
}
```

Omit `Content-Type` for multipart uploads.

### Join button logic

Trust server `can_join` — do not reimplement the 15-minute window on the client (clock skew). Optionally grey out Join when `false` and show “Available closer to appointment time”.

---

## 15. Test accounts & curl cheatsheet

Seeded verified hakeems (password `Test@1234`), e.g.:

- `hakeem.rehman@yopmail.com`

```bash
API=http://127.0.0.1:8000/api/v1

# Login
TOKEN=$(curl -s -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"hakeem.rehman@yopmail.com","password":"Test@1234"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Dashboard
curl -s "$API/hakeem/dashboard" -H "Authorization: Bearer $TOKEN" | jq

# Calendar August 2025
curl -s "$API/hakeem/availability?month=8&year=2025" -H "Authorization: Bearer $TOKEN" | jq

# Toggle a date available
curl -s -X PATCH "$API/hakeem/availability/2025-08-10" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"is_available":true,"slots":[{"start_time":"09:00:00","end_time":"17:00:00"}]}' | jq

# Weekly default Mon–Fri
curl -s -X PUT "$API/hakeem/availability/weekly-default" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"days":[{"day_of_week":0,"is_available":true,"slots":[{"start_time":"09:00:00","end_time":"17:00:00"}]},{"day_of_week":1,"is_available":true,"slots":[{"start_time":"09:00:00","end_time":"17:00:00"}]},{"day_of_week":2,"is_available":true,"slots":[{"start_time":"09:00:00","end_time":"17:00:00"}]},{"day_of_week":3,"is_available":true,"slots":[{"start_time":"09:00:00","end_time":"17:00:00"}]},{"day_of_week":4,"is_available":true,"slots":[{"start_time":"09:00:00","end_time":"17:00:00"}]},{"day_of_week":5,"is_available":false,"slots":[]},{"day_of_week":6,"is_available":false,"slots":[]}]}' | jq

# Profile
curl -s "$API/hakeem/me/profile" -H "Authorization: Bearer $TOKEN" | jq

# Patch bio
curl -s -X PATCH "$API/hakeem/me/profile" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"bio":"Practicing Unani medicine with a focus on digestive health and herbal formulation for holistic care."}' | jq

# Earnings
curl -s "$API/hakeem/earnings/summary" -H "Authorization: Bearer $TOKEN" | jq
curl -s "$API/hakeem/earnings/payout-history?limit=20" -H "Authorization: Bearer $TOKEN" | jq
curl -s -X POST "$API/hakeem/earnings/request-payout" -H "Authorization: Bearer $TOKEN" | jq
```

### Signup flow (new hakeem)

```bash
# 1) Upload ID
curl -s -X POST "$API/uploads/verification-document" \
  -F 'document_type=national_id' -F 'file=@./id.jpg;type=image/jpeg'

# 2) Upload license
curl -s -X POST "$API/uploads/verification-document" \
  -F 'document_type=license' -F 'file=@./license.pdf;type=application/pdf'

# 3) Apply (paste document_url values from steps 1–2)
curl -s -X POST "$API/auth/signup/hakeem" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "new.hakeem@yopmail.com",
    "password": "Test@1234",
    "full_name": "Dr. Yusuf Al-Rashid",
    "national_id_number": "42101-1234567-1",
    "national_id_document_url": "<URL_FROM_STEP_1>",
    "license_number": "UNANI-2024-88",
    "license_document_url": "<URL_FROM_STEP_2>",
    "specializations": ["digestive_health"],
    "years_of_experience": 8,
    "city": "Karachi",
    "languages_spoken": ["urdu", "english"],
    "consultation_fee": 2500,
    "bio": "Practicing Unani medicine for over 8 years specializing in chronic digestive conditions.",
    "training_institute": "Ibn Sina Institute",
    "reason_for_joining": "To bring classical Hikmat care to more patients through a trusted digital platform.",
    "agrees_to_terms": true
  }'
```

Then an admin must approve via `/admin/hakeem-applications/{id}/approve` before the public profile and verified badge appear.

---

## Endpoint index (quick reference)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/uploads/verification-document` | — | Upload ID/license file |
| `POST` | `/auth/signup/hakeem` | — | Create hakeem + pending application |
| `POST` | `/auth/login` | — | Login (all roles) |
| `POST` | `/auth/refresh` | — | Refresh tokens |
| `GET` | `/auth/me` | Bearer | Current user |
| `GET` | `/hakeems/{user_id}/profile` | — | Public verified profile |
| `GET` | `/hakeem/dashboard` | Hakeem | Today overview |
| `GET` | `/hakeem/availability` | Hakeem | Month calendar dots + upcoming |
| `PUT` | `/hakeem/availability/weekly-default` | Hakeem | Recurring weekly hours |
| `PATCH` | `/hakeem/availability/{day}` | Hakeem | Per-date override |
| `GET` | `/hakeem/earnings/summary` | Hakeem | Balances / month totals |
| `GET` | `/hakeem/earnings/payout-history` | Hakeem | Paginated payouts |
| `POST` | `/hakeem/earnings/request-payout` | Hakeem | Queue payout (≥ PKR 1000) |
| `GET` | `/hakeem/me/profile` | Hakeem | Own full profile |
| `PATCH` | `/hakeem/me/profile` | Hakeem | Edit bio/specs/fee/langs/city |
| `GET` | `/admin/hakeem-applications` | Admin | List applications |
| `GET` | `/admin/hakeem-applications/{id}` | Admin | Application detail |
| `POST` | `/admin/hakeem-applications/{id}/approve` | Admin | Approve |
| `POST` | `/admin/hakeem-applications/{id}/reject` | Admin | Reject |
| `POST` | `/admin/hakeem-applications/{id}/request-more-info` | Admin | Needs more info |

Related (not under `/hakeem` but used by hakeem UI): connections accept/reject, conversations/chat, community feed — see sibling docs in `/docs`.
