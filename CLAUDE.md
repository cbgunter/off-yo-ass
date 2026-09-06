# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Off Yo Ass is a single-user (`cbgunter@gmail.com` only) health/fitness PWA deployed at
`oya.caseyhunter.net`. Its one job: every day at 15:45 it reads Garmin recovery data, Google
Calendar, and weather, and pushes one specific, bluntly-worded prescription — then closes the loop
with an evening check-in, a bedtime nudge, a weekly question, and always-available free-text notes.
`BRANDING.md` (repo root) is the source of truth for every UI and copy decision: warm paper/ink
palette, Instrument Serif + IBM Plex fonts, no streaks/badges/emoji/exclamation marks/em-dashes,
no cheerleading. Read it before touching any UI copy or the coach's system prompts.

## Repo layout — three independent projects

```
oya/              Python backend (FastAPI + Lambda workers) — its own pyproject.toml/uv.lock
infra/            AWS CDK app (Python) — its own pyproject.toml/uv.lock, separate venv
web/              React + TypeScript frontend (Vite) — its own package.json
tests/            Backend tests (pytest, run from repo root against oya/)
scripts/          One-time credential/config bootstraps, run locally by the user (see below)
BRANDING.md       Design system + voice rules, source of truth for tokens.css and every prompt
```

`infra/` never imports from `oya/` (or vice versa) — they're separate Python environments. Shared
literal constants (SSM parameter names, etc.) are intentionally duplicated in both rather than
imported, since there's no shared package between them.

## Commands

### Backend (`oya/`, from repo root)
```
uv sync                                   # install deps
uv run pytest -q                          # full suite
uv run pytest tests/test_coach.py -q      # one file
uv run pytest tests/test_coach.py::test_generate_call_accepts_a_clean_first_attempt  # one test
uv run ruff check .                       # lint (select = E,F,I,UP,B; B008 ignored for Depends())
```

### Infra (`infra/` — separate venv, run from `infra/`)
```
uv sync
uv run pytest -q
uv run ruff check .
npx --yes aws-cdk@2 synth --all           # validates cleanly with no AWS creds (no context lookups)
npx --yes aws-cdk@2 deploy <StackName> --require-approval never
```
`cdk synth`/`deploy` need `infra/build/lambda` to exist first — run `bash scripts/build_lambda.sh`
from repo root (stages the FastAPI app as a Lambda package via `uv pip install --target`, no
Docker; strips `boto3`/`botocore` since the Lambda runtime image already provides them).

### Web (`web/`)
```
npm ci
npm run dev                               # vite dev server, proxies /api to localhost:8000
npm run build                             # tsc -b && vite build
npm run lint                              # eslint .
npm run test                              # vitest run
npx vitest run src/routes/Health.test.tsx # one file
```

### CI (`.github/workflows/ci.yml`)
Three jobs on every push/PR: `web` (lint+test+build), `backend` (ruff+pytest), and `infra-synth`
(builds the Lambda package, then `cdk synth --all` with no AWS credentials — this is what catches
infra bugs on every PR without needing deploy permissions). Deploys happen separately via
`deploy.yml` on push to `main`, through a GitHub OIDC role (`GitHubActionsOffYoAssRole`), and
deploy exactly the stacks it names in its `cdk deploy` command — if a new CDK-level input is added
to `infra/app.py` (a new `os.environ.get(...)`), it must also be added to that workflow's `env:`
block or a deploy will silently reset it to empty in production (this has happened before).

## Backend architecture (`oya/`)

**Single DynamoDB table, single user.** `oya/store/table.py` is the only module that touches
boto3's DynamoDB API. `pk = "U#cbg#<ENTITY>"`, `sk` is an ISO date (one row/day, e.g. `CALL`) or
ISO timestamp (multiple rows/day, e.g. `NOTE`, `MEAL`) depending on the entity — check existing
sibling entities before picking a convention for a new one. `Entity` class constants prevent typos;
`put_item`/`query_range`/`query_all`/`get_latest` are the only four access patterns needed.
`_to_dynamodb_value` auto-converts `float → Decimal` recursively — callers never do this manually.

**Settings** (`oya/settings.py`): every secret follows the same `foo: str = ""` /
`foo_param: str = "/oya/..."` pair, with a `resolved_foo()` method returning the direct value if
set, else fetching from SSM (`_fetch_ssm_secret`, `lru_cache`d). This is what makes tests fast (env
var bypasses SSM entirely) without adding any test-only code path. `boto3` itself is imported
lazily inside functions that need it in some modules — it ships in the Lambda runtime image and is
deliberately not a hard dependency of the deploy package (see `scripts/build_lambda.sh`).

**API** (`oya/api/`): FastAPI app (`app.py`) behind Mangum (`handler.py`), one router module per
concern, each `APIRouter(prefix="/api/x")`. Every protected route takes
`user: User = Depends(get_current_user)` as its last parameter (per-route, not router-level).
Every module uses `from __future__ import annotations`, which stringifies `-> None` and breaks
FastAPI's response inference — every 204/`None`-returning route needs an explicit
`response_model=None` (see the comment in `oya/api/push.py` for the full explanation; don't
rediscover this the hard way). No CORS middleware exists anywhere — everything is same-origin
through CloudFront (`web/src/lib/api.ts` fetches `` `/api${path}` `` with `credentials: 'include'`).

**Domain layer** (`oya/domain/`) holds pure logic shared between the API and the workers so both
see identical numbers by construction — `recovery.py`'s `get_recovery_snapshot()` and `food.py`'s
`get_food_snapshot()` are each called from both a route and `oya/workers/coach.py`.
`baselines.py`'s `compute_baseline()` is the one honesty-rule implementation: no delta is ever
reported below a minimum history window, just an explicit "building baseline" state — every new
metric needing a trend should reuse this rather than hand-rolling an average. Note `food.py`'s
lookback window is deliberately wider than the 30-day minimum (unlike `recovery.py`'s exact
31-day window) because food logging has real gaps, while Garmin's daily sync doesn't — copying
`recovery.py`'s tight windowing for a sparser data source makes a full baseline unreachable.

**Prompts** (`oya/prompts/`) hold Pydantic response schemas + system prompts for every LLM call —
this is where BRANDING.md's voice rules compile into text. `oya/prompts/validate.py` is the
mechanical backstop (`find_violations`, `is_clean`, `validate_call_text`): exclamation marks,
emoji, em/en-dashes, and a cheerleading-phrase denylist. It deliberately does not try to detect
things like rhetorical questions algorithmically — that stays a system-prompt instruction. The
structured-output call pattern is `client.messages.parse(model=..., system=..., messages=[...],
output_format=SomeModel)` → `.parsed_output`; the coach's system prompt is cached
(`cache_control: {"type": "ephemeral"}`) since it's identical every call, while lighter one-off
calls (notes, meal analysis) pass a plain string. `oya/workers/coach.py`'s `generate_call()` shows
the full pattern worth copying for any new LLM-driven feature: generate → mechanically validate →
regenerate once with the violation named → fall back to a template built directly from numbers,
so a bad model day never becomes bad output. Every external integration call in
`build_context()` is individually wrapped in `try/except` degrading to an "X unavailable." string
— one integration having a bad day must never take the whole call down.

**Workers** (`oya/workers/`): five scheduled Lambdas via `aws_scheduler.CfnSchedule` (EventBridge
*Scheduler*, not classic Rules — Rules have no timezone concept and a fixed UTC cron drifts an
hour every DST transition). All five share `infra/stacks/workers_stack.py`'s
`_scheduled_function()` helper.

| Time (ET) | Worker |
|---|---|
| 08:00 | `sync_garmin` |
| 15:45 | `coach` — the daily call |
| 20:30 | `checkin` — fixed-copy reminder, no LLM |
| 21:00 | `bedtime` — deterministic nudge from tomorrow's first calendar event, no LLM |
| Sun 19:00 | `weekly_question` |

## Infra architecture (`infra/`)

CDK stacks, one account/region (`466850516129`, `us-east-1`), wired in `infra/app.py`:
`OyaGithubOidc` (deployed once by hand, never by CI) → `OyaNetwork` → `OyaData` (DynamoDB table +
S3 buckets) → `OyaApi` (Lambda + HTTP API, takes `table`/bucket refs from `OyaData`) →
`OyaFrontend` (S3 + CloudFront, proxies `/api/*` to `OyaApi`'s HTTP API) → `OyaWorkers` (the five
scheduled Lambdas, also takes `table` from `OyaData`). Cross-stack values are passed as
keyword-only construct references (`table=data.table`), not ARNs/strings.

Two CloudFront details that look like bugs if "fixed": the `api/*` behavior path pattern has **no
leading slash** (CloudFront strips it before matching — a leading slash silently never matches),
and its origin request policy is `ALL_VIEWER_EXCEPT_HOST_HEADER`, not `ALL_VIEWER` (forwarding the
Host header breaks API Gateway with a 403 that the SPA's error fallback then masks as a fake 200).
Both have dedicated regression tests in `infra/tests/test_frontend_stack.py` — if a change makes
those tests fail, the tests are very likely correct and the change is the bug.

IAM for SSM: `ssm:GetParametersByPath` authorizes against the bare parameter path ARN, while
`ssm:GetParameter`/`PutParameter` need the `/*` children pattern — granting only one form 403s on
whichever action needs the other (`_scheduled_function`'s `ssm_read_write_path` grants both
together; confirmed against a real deploy, not by inspection).

Every Lambda environment variable a worker or the API reads via `oya/settings.py` must be
explicitly set in the corresponding CDK stack's `environment={...}` dict — granting IAM read
access to an SSM parameter is not the same as telling the Lambda the parameter's *name*; this class
of bug has shipped twice (a missing `OYA_VAPID_PRIVATE_KEY_PARAM` broke all push notifications
silently until a real subscription existed to notify).

## Frontend architecture (`web/`)

`web/src/styles/tokens.css` is the only place a color, font, or spacing value is defined — it's a
direct translation of `BRANDING.md`; nothing else should hardcode one (`global.css` holds the
actual component classes built from those tokens). Routes live in `web/src/routes/`, each a
`.screen` wrapped by `<Gate>` in `App.tsx` (session-loading + redirect-to-sign-in). `Nav.tsx`'s
`LINKS` array is the single source of nav entries — not every route is in it (e.g. `/question` is
reachable only via a push notification's deep link, not from the nav).

`web/src/lib/api.ts` is a thin same-origin JSON client (`api.get`/`api.post`); it cannot send
`FormData` (unconditional `Content-Type: application/json`, and `...init` spreads after
`headers`), which is why binary uploads (meal photos) go as base64 inside the JSON body rather
than multipart or a presigned S3 URL — see `oya/api/meals.py` and `web/src/lib/image.ts` for the
downscale-to-JPEG-then-base64 pattern.

## Testing patterns

Backend tests use `moto[dynamodb,s3]`'s `mock_aws()` — the `dynamodb_table` fixture in
`tests/conftest.py` sets every `TEST_ENV` var via `monkeypatch`, clears `get_settings()`'s
`lru_cache`, and creates the table (and S3 bucket) inside the mock context; `authed_client` layers
a signed-in session on top. Anthropic is mocked one of two ways depending on where the client is
constructed: patch the `Anthropic` class directly in a route module's namespace
(`patch("oya.api.notes.Anthropic", ...)`) for routes that build a client inline, or patch a
module's `_client()` factory function (`patch("oya.workers.coach._client", ...)`) where one exists
specifically to make this patchable. Every new secret added to `oya/settings.py` needs a
corresponding fake value added to `tests/conftest.py`'s `TEST_ENV`, or tests will try to hit real
SSM. Infra tests synthesize a stack with `aws_cdk.assertions.Template` against a `TestSupport`
stack providing any imported constructs (table, bucket) the stack under test needs.

Every real production bug found in this project so far was invisible to local tests and only
surfaced against a live deploy or a real API call (the CloudFront path pattern, the Host header
forwarding, the IAM ARN split, a missing Lambda env var, a missing `cdk deploy` env passthrough) —
each was fixed with a paired regression test, but new infra/integration work should still expect
to verify against the real deployed stack, not just the local suite.

## Bootstrap scripts (`scripts/`)

Any script needing a real login (Garmin password, Google OAuth consent) is designed to be run by
the user, locally, never fed credentials through the assistant — `scripts/bootstrap_calendar.py`
opens the user's own browser to Google's consent screen and catches the redirect on
`localhost:8080`; nothing is typed into a terminal. `scripts/build_lambda.sh` and
`scripts/resolve_weather_grid.py` are plain config/build steps with no credentials involved.
`scripts/backfill_garmin.py` (needs the user's AWS creds, run locally) re-fetches a stretch of
past days one at a time so `oya/domain/recovery.py`'s 30-day baselines can establish without
waiting a month; the nightly `sync_garmin` also re-fetches a trailing `BACKFILL_DAYS` window each
run, since Garmin posts sleep/HRV a day or two behind resting HR and a day missed at first sync
was otherwise never revisited.
