# Motor Assistant upgrade, audit and deployment notes

Last verified: 2026-10-27

This document describes the incremental upgrade of the existing Django +
Gemini motorcycle/car assistant. It is not a rebuild: the original guided
diagnostic flow, existing tables, uploads, templates and the GLB viewer asset
are preserved. New behaviour is added behind the `structured: true` chat
option or on the structured assistant endpoints.

## 1. Audit summary

Baseline before the upgrade:

- Worktree clean; no committed `.env` or active `GEMINI_API_KEY`.
- `google-genai` 2.31.0, Django 6.0.5, Python 3.14.8.
- `python manage.py check` passed.
- Baseline test suite: 138 passed.
- Existing GLB motorcycle model: 49 named mesh nodes.
- No verified manufacturer service-manual dataset was supplied.
- No production database or production backup was available in this checkout.

The upgrade keeps the legacy browser-history/guided workflow for requests
without `structured: true`. The structured workflow uses server-side
`Conversation`/`ChatTurn` memory, ORM keyword retrieval, local safety rules,
and an explicitly labelled offline answer when Gemini is unavailable.

## 2. What changed

### Safety and assistant pipeline

- `apps/core/services/safety.py`: multilingual critical rules for brakes, fuel
  leaks, fire/electrical smoke, severe overheating, rod knock/oil starvation,
  and steering/tyre failure. Critical warnings are never downgraded because a
  turn is phrased as a question, and procedure exclusions are only applied to
  low-severity informational rules.
- Local safety assessment runs before AI retrieval and is pinned above model
  text. A symptom or photo is always described as a possibility, not proof.
- `apps/core/services/intake.py`: language detection, profile extraction and
  missing-question selection in English, Filipino/Tagalog and
  Hiligaynon/Ilonggo.
- `apps/core/services/assistant.py`: structured orchestrator. Stored/extracted
  vehicle data wins over model guesses. The AI receives only approved local
  records as technical evidence.
- `apps/core/services/structured.py`: bounded response normalisation. Model
  citations not present in local evidence are discarded. Model-supplied part
  numbers and compatibility claims are withheld unless the same part came from
  a stored local record.
- `apps/core/services/ai.py`: central Gemini access, env-driven model name,
  bounded SDK retries, friendly error categories, and no raw provider errors
  sent to the browser.
- `apps/core/services/offline.py`: evidence-backed offline answers with clear
  "Gemini was not used" labelling. Offline photo answers now explicitly say
  the photo was not analysed.

### Memory and endpoints

- New `Conversation` and `ChatTurn` tables. Client history is not authoritative
  for structured AI memory.
- Endpoints:
  - `POST /jarvis/chat/` (legacy path unchanged unless `structured: true`)
  - `POST /jarvis/image/upload/`
  - `GET /jarvis/image/<id>/`
  - `GET /jarvis/status/`

### Private diagnostic photos

- Uploads are decoded, re-encoded to a bounded JPEG, and stripped of unsafe
  metadata before storage.
- Files are stored under `PRIVATE_MEDIA_ROOT`, not `MEDIA_ROOT`.
- The serving view checks ownership and returns `Cache-Control: private`.
- The original filename is sanitised for the download header.

### 3D viewer

- `static/motor/viewer.js` maps the real GLB node names, disables components
  that are not modelled, supports `?part=engine` deep links and only runs the
  cinematic tour over available components. Missing sprocket, battery, brake
  caliper/pads/hose and internal engine parts are not faked.

### Security and configuration

- `GEMINI_API_KEY` stays server-side. No key is rendered into templates or JS.
- `AUTO_LOGIN_DEV` is opt-in and defaults off; the known-password superuser
  creation was removed.
- Cache-backed per-user rate limits for chat and uploads.
- Env-driven SQLite/MySQL selection.
- `.env.example` documents required production values.

## 3. Migrations

New migrations:

```text
apps/core/migrations/0003_conversation_imageupload_maintenanceitem_and_more.py
apps/core/migrations/0004_repairrecord_source_turn.py
apps/core/migrations/0005_repairrecord_limitations_repairrecord_verification.py
apps/core/migrations/0006_remove_maintenanceitem_core_mainte_user_id_282077_idx_and_more.py
apps/motor/migrations/0003_diagnosticsymptom_aliases_and_more.py
apps/motor/migrations/0004_alter_troubleshootingguide_is_verified.py
apps/motor/migrations/0005_remove_part_compatibility_verified_and_more.py
```

`0006` intentionally removes the rider-garage, repair-history and maintenance
tables and their saved records. `motor.0005` removes the parts-library columns
and the `PartFitment` table. The pre-existing `Part` table and its base fields
remain for diagnostic knowledge. Back up the database before applying these
removals.

Verified state on a fresh SQLite database:

```text
core
 [X] 0001_initial
 [X] 0002_geminiusagetracker
 [X] 0003_conversation_imageupload_maintenanceitem_and_more
 [X] 0004_repairrecord_source_turn
 [X] 0005_repairrecord_limitations_repairrecord_verification
 [X] 0006_remove_maintenanceitem_core_mainte_user_id_282077_idx_and_more
motor
 [X] 0001_initial
 [X] 0002_diagnosticsymptom_safety_warning_and_more
 [X] 0003_diagnosticsymptom_aliases_and_more
 [X] 0004_alter_troubleshootingguide_is_verified
 [X] 0005_remove_part_compatibility_verified_and_more
```

`python manage.py makemigrations --check --dry-run` prints
`No changes detected`.

The original schema migrations are additive; the two latest migrations are
deliberately destructive for the removed features. Back up the database and
`media/` before migrating.

## 4. Backups and migration procedure

### SQLite (default)

```powershell
python manage.py migrate --noinput
Copy-Item db.sqlite3 "db.sqlite3.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

Take the copy while the application is stopped, or use SQLite's backup API /
`.backup` command. Copy `private_media/` and `media/` separately; they are not
inside the database.

### MySQL / MariaDB

```powershell
$env:USE_MYSQL = '1'
mysqldump --single-transaction --routines --triggers `
  -u root -p motor_assistant_db > "motor_assistant_db-$(Get-Date -Format yyyyMMdd-HHmmss).sql"
python manage.py migrate --noinput
```

Restore is the reverse: stop the app, restore the dump, restore uploads.
Django 6 requires MariaDB 10.11 or later (or a supported MySQL release).

### Seed data (optional, idempotent)

```powershell
python manage.py seed_knowledge
```

Verified output in this checkout:

```text
Seeded symptoms=6 guides=12 questions=12.
Bundled sources are general references. Re-check each record against the manual
for the exact model and variant before relying on its measurements or part
guidance.
```

Seed records are not a substitute for a manufacturer manual. Part numbers and
procedures remain unverified unless a checked source was recorded.

## 5. Environment variables

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Long random production secret. |
| `DJANGO_DEBUG` | `0` in production. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated production hostnames. |
| `DJANGO_SECURE_SSL_REDIRECT` | HTTPS redirect when `DEBUG=0`. |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS lifetime when `DEBUG=0`. |
| `AUTO_LOGIN_DEV` | Development-only auto-login; keep `0` in production. |
| `USE_MYSQL` | `1` selects MySQL/MariaDB. |
| `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT` | Database connection. |
| `DJANGO_CACHE_BACKEND`, `DJANGO_CACHE_LOCATION` | Rate-limit cache. Use a shared cache for multiple workers. |
| `GEMINI_API_KEY` | Server-side Gemini credential. |
| `GEMINI_MODEL` | Gemini model ID. Confirm availability in your account. |
| `GEMINI_FALLBACK_MODEL` | Optional fallback model ID. |
| `GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_RETRIES` | Bounded provider retry policy. |
| `GEMINI_DAILY_REQUEST_LIMIT` | Application-side daily request budget, not a Google quota claim. |
| `GEMINI_INPUT_IMAGE_SUPPORTED` | Set `0` to disable photo analysis. |
| `AI_PROVIDER`, `AI_API_BASE_URL`, `AI_API_KEY`, `AI_EXPLANATION_LEVEL` | Optional OpenAI-compatible provider / explanation level. |
| `ASSISTANT_MAX_CONTEXT_TURNS`, `ASSISTANT_SUMMARY_TRIGGER_TURNS`, `ASSISTANT_MAX_MESSAGE_CHARS` | Assistant bounds. |
| `IMAGE_UPLOAD_MAX_BYTES`, `IMAGE_UPLOAD_MAX_PIXELS`, `IMAGE_UPLOAD_MAX_DIMENSION` | Upload validation/re-encoding limits. |
| `CHAT_RATE_LIMIT_PER_MINUTE`, `UPLOAD_RATE_LIMIT_PER_MINUTE` | Per-user rate limits. |

Multi-worker deployments must not use the default `LocMemCache` for rate
limits. Options include the database cache:

```powershell
$env:DJANGO_CACHE_BACKEND = 'django.core.cache.backends.db.DatabaseCache'
$env:DJANGO_CACHE_LOCATION = 'jarvis_rate_limit_cache'
python manage.py createcachetable
```

or Redis/Memcached via a supported Django cache backend.

## 6. Local setup commands

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_knowledge
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`, sign in, choose **Smart** mode and ask a
question. Photos are stored privately and remain available through the
ownership-checked image endpoint.

## 7. Verification results

Run on this checkout on 2026-10-27:

```text
$ python -m pytest -q
164 passed in 18.58s
# 1 upstream DeprecationWarning from google-genai/Python 3.17 readiness

$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py makemigrations --check --dry-run
No changes detected

$ node --check static/motor/viewer.js
(no output; exit 0)

$ python (inline home-page script extraction) + node --check
script blocks: 1 bytes: 88586
node exit: 0

$ python (live Gemini connectivity check)
model: gemini-3.1-flash-lite
live call: OK
reply: OK
usage: prompt=18 candidate=1 total=19 tokens
```

`DJANGO_DEBUG=0 python manage.py check --deploy` reports only
`security.W009` when deliberately run with a short temporary secret. Use a
long random `DJANGO_SECRET_KEY` in production.

### Live smoke test

A fresh local SQLite database was migrated and seeded, then the development
server was exercised in a real browser:

- Login succeeded with a locally created smoke-test user.
- Smart-mode chat returned an offline structured answer with
  `severity: critical` and the brake safety warning first.
- The response included local record citations without exposing model-created
  specifications.
- `/motor/viewer/?part=engine` loaded the GLB (`49 meshes`, `8,944 faces`),
  showed the engine deep link and no browser console warnings.
- A browser-generated JPEG uploaded through the real endpoint:
  `200`, re-encoded to JPEG, `original_name` ending `.jpg`, private image URL.
- The private image served with `Content-Type: image/jpeg` and
  `Cache-Control: private, max-age=300`.
- A Tagalog follow-up returned a Tagalog critical brake warning and persisted
  the same server-side conversation.
- `/jarvis/status/` returned `ai_configured: true`, quota metadata and the
  three supported languages without exposing any credential.

After the smoke test, the scratch database was reset and the uploaded test
image was deleted; no smoke-test user or uploaded file remains in the checkout.

## 8. Deployment checklist

1. Provision a supported Python environment and install `requirements.txt`.
2. Set a long random `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, the real
   `DJANGO_ALLOWED_HOSTS`, and HTTPS/HSTS values in the server environment.
3. Point the database at MariaDB 10.11+ or leave SQLite only for a small
   single-process deployment.
4. Configure a shared cache for rate limits if running more than one worker.
5. Run `python manage.py migrate --noinput`.
6. Run `python manage.py collectstatic --noinput`.
7. Make `media/` and `private_media/` writable by the app user. Do not expose
   `private_media/` through nginx or another public static handler; it is
   served only by the ownership-checked Django view.
8. Configure TLS at the reverse proxy and forward the original scheme.
9. Start the WSGI/ASGI server (for example gunicorn/uwsgi/Waitress) and keep
   the process environment secret.
10. Verify `/jarvis/status/` while logged in without printing the key, then
    run one structured chat and one photo upload.
11. Schedule database and upload backups. Test a restore.
12. Keep `seed_knowledge` optional; review each seeded record before using its
    measurements on a specific vehicle.

## 9. Unfinished work and blockers

- Live Gemini connectivity was verified with one minimal text call using
  `gemini-3.1-flash-lite` (reply `OK`; 19 tokens). Full live structured-chat
  and photo-analysis responses were not exercised; those paths rely on mocked
  provider tests and offline fallbacks.
- No production database or real production backup existed here. Migration
  safety was verified on fresh SQLite test databases only. MySQL was not
  exercised because no live MariaDB/MySQL server was available.
- The bundled knowledge is general reference material, not verified
  manufacturer data for a specific model/variant. Torque values and fluid
  specifications remain unverified. Seed part numbers are references, not a
  compatibility guarantee.
- The GLB does not model the front sprocket/chain, battery/fuse box, brake
  caliper/pads/hose, or internal engine parts. Those components are explicitly
  disabled rather than simulated.
- Retrieval is ORM keyword/intent scoring, not vector search. It is cheap and
  transparent but may miss paraphrases outside its token/intent vocabulary.
- The in-app rate limiter is cache-backed; multi-worker deployments need a
  shared cache as described above.
- Automatic photo analysis is only possible when the provider is configured
  and `GEMINI_INPUT_IMAGE_SUPPORTED=1`; offline answers disclose that the photo
  was not analysed.
