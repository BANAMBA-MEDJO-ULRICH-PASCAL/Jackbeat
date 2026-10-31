# Jackbeat — Evaluation & Improvements (October 2026)

This document records a full review of the Jackbeat site (security, features,
data integrity, deployment, UX, accessibility, performance, SEO and code
quality), what was found, what was changed, and how it was verified.

---

## 1. Verdict

Jackbeat had a clear, valuable mission and a polished design, but it was **not
safe to run in public**. Several issues let an outsider take control of the
admin's session or wipe the archive. Two latent deployment problems meant the
*next* deploy could fail. Everything below marked **Fixed** is done in this
change.

| Area | Before | After |
|---|---|---|
| Security | Several critical holes (stored XSS, CSRF on every admin action, default password) | CSP with nonces, CSRF everywhere, 2FA, lockout, audit log, hardened config |
| Admin editing | Partial edit forms, no history, no CSRF | Full editing, "save & publish", contributor's original kept, field-level history, duplicate merge |
| Languages | French only | Fully bilingual FR / EN (UI, charts, PDF, CSV, admin, story page, bilingual content fields) |
| Data integrity | Fake placeholder artists published; seed wiped admin edits | Placeholder artists flagged and blocked from publication; seed never overwrites |
| Deployment | Next deploy could fail (2 independent causes) | Both fixed and verified on PostgreSQL 16 |
| Tests | None | 57 automated tests + end-to-end browser run |

---

## 2. Findings

Severity: **Critical** = remote takeover or data loss possible · **High** =
serious, exploitable or deploy-breaking · **Medium** · **Low**.
"Verified" means the problem was reproduced on the original code before fixing.

### Critical

| # | Finding | Evidence | Status |
|---|---|---|---|
| C1 | **Stored XSS via a song title.** Titles were placed inside `onclick="playYoutube('…','{{ titre|e }}')"`. HTML-escaping does not protect a JavaScript string in an attribute: the browser decodes `&#39;` back to `'`. A contributed title such as `x',document.title='XSS','` executes in every visitor's browser once approved. | Verified in Chromium: page title became `XSS-FIRED`. | **Fixed**: no inline JS anywhere; data travels in `data-*` attributes and is inserted with `textContent`. |
| C2 | **`javascript:` links accepted as "YouTube links".** `lien_youtube` was not validated and was rendered as a raw `href` on the homepage and **in the admin moderation list, before approval**. Clicking "Vidéo" in the admin list would run the attacker's code with the admin's session. | Code review (field had no validator; rendered as `href`). | **Fixed**: only real YouTube URLs are accepted (server-side), and links are rebuilt from the extracted video ID. |
| C3 | **No CSRF protection on admin actions.** `CSRFProtect` was never initialised; approve / reject / **delete** were plain `GET` links; the edit forms had no token. Any web page visited by a logged-in admin could silently delete artists (e.g. with an `<img src=".../supprimer">`). | Code review; `GET /admin/artiste/1/action/supprimer` deleted the artist. | **Fixed**: global CSRF protection; every state change is a `POST` with a token; logout too. |
| C4 | **Default credentials in production.** `ADMIN_PASSWORD` fell back to `jackbeat2024` and `SECRET_KEY` to a public string in *all* configurations, production included. | Verified: `admin / jackbeat2024` logged in. | **Fixed**: production refuses to start without a strong `SECRET_KEY` and never creates an admin with a weak password. The dev fallback only exists in development. |

### High

| # | Finding | Status |
|---|---|---|
| H1 | **Cancelling "Delete permanently?" still deleted.** The page-fade script in `main.js` intercepted every link click and navigated even when the confirm dialog had cancelled it. *Verified*: 7 artists → 6 after clicking **Cancel**. | **Fixed** (navigation is no longer intercepted; deletes are POST forms with a proper confirm). |
| H2 | **Deploy breaker #1 — seed vs. foreign keys.** `build.sh` re-ran the demo seed on every deploy, and it bulk-deleted the demo works. On PostgreSQL, as soon as anyone likes or comments on a demo song, that delete violates a foreign key and `build.sh` (with `errexit`) fails the deploy. It also overwrote any admin correction to demo entries on every deploy. *Verified on PostgreSQL 16*: `ForeignKeyViolation`, exit code 1. | **Fixed**: the seed only inserts what is missing and fills empty fields; `--sync` updates in place and never deletes. |
| H3 | **Deploy breaker #2 — unpinned SQLAlchemy.** SQLAlchemy 2.1 changed the default PostgreSQL driver to `psycopg` (v3), but only `psycopg2-binary` is installed. A fresh build installs 2.1 → "No module named psycopg" → the site cannot reach its database. *Verified* in this environment. | **Fixed**: SQLAlchemy pinned to 2.0.55 **and** the URL names the driver explicitly (`postgresql+psycopg2://`). |
| H4 | **Admin login had no brute-force protection**, used a 1-year "remember me" cookie, and sessions survived password changes. | **Fixed**: lockout per IP and per account (DB-backed, works across workers), 2-hour sessions, session fixation prevented, password change / 2FA change logs out all other sessions, constant-time behaviour for unknown usernames. |
| H5 | **More DOM XSS sinks**: the map panel and the search suggestions built HTML strings from artist names / titles with `innerHTML`. | **Fixed**: built with DOM APIs and `textContent`; URLs checked. |
| H6 | **Spoofable visitor identity.** Likes and anti-spam limits used the *first* `X-Forwarded-For` value, which the client controls (unlimited likes, bypassed comment limits). The "anonymised" IP was an unsalted SHA-256, which is reversible for IPv4 (only 4 billion values). | **Fixed**: `ProxyFix` with a configurable number of trusted proxies, and a keyed HMAC (`IP_HASH_SALT`). |
| H7 | **Fake data published automatically.** A work submitted for an unknown artist created that artist with a made-up region (`Centre`) and type (male soloist); approving the work silently published that fake profile, skewing the map and statistics. Artist matching also ignored pending artists, creating duplicates. | **Fixed**: such profiles are flagged "to complete", cannot be published until an admin saves them, and the work stays hidden until then. Contributors can now give the artist's region/type. Matching is case-insensitive over all non-rejected artists. |

### Medium

| # | Finding | Status |
|---|---|---|
| M1 | No security headers (no CSP, clickjacking possible, no HSTS, no `nosniff`). | **Fixed**: strict CSP with per-request nonces (`script-src-attr 'none'`, no `unsafe-eval`), HSTS, `X-Frame-Options: DENY`, Referrer/Permissions policies, `no-store` on admin pages. CDN files pinned with Subresource Integrity. |
| M2 | Open redirect through `?next=` on login, and redirects to the raw `Referer`. | **Fixed**: same-host check on every redirect target. |
| M3 | CSV formula injection (`=HYPERLINK(...)` titles) in exports; the public dashboard linked to the admin-only CSV (visitors hit the login page). | **Fixed**: cells neutralised; new public open-data CSV without any personal data. |
| M4 | Admin sidebar counters forced to 0 on most pages by stray `{% set pending_… = 0 %}`. | **Fixed**. |
| M5 | Public pages listed works whose artist was pending/rejected (their artist link 404'd). | **Fixed**: one `Oeuvre.publiees()` rule used everywhere. |
| M6 | The `build.sh` migration silently stopped working on PostgreSQL after the first "column exists" error (aborted transaction never rolled back). | **Fixed**: new `migrations.py` inspects the schema and adds missing columns, one transaction each. Verified on SQLite and PostgreSQL with an old-schema database. |
| M7 | `python app.py` ran the Werkzeug debugger on `0.0.0.0` (remote code execution for anyone on the same network). | **Fixed**: binds to `127.0.0.1`. |
| M8 | View counters incremented on every reload (Top charts trivially inflatable). | **Fixed**: one view per visitor session. |
| M9 | PDF report: unauthenticated and regenerated on every request (cheap DoS); `≥` rendered as a broken glyph; database text injected into ReportLab markup. | **Fixed**: 5-minute cache per language, rate limit, escaped text, glyph replaced. |
| M10 | No rate limiting on submissions, comments, likes or reports. | **Fixed**: per-IP limits + invisible honeypot field against bots. |

### Low / UX / accessibility / SEO

- Two search widgets in the navbar sharing the same element IDs (the second never worked) and a duplicated "Explorer" link → **fixed**.
- Dashboard filter dropdowns rendered as a borderless vertical list, and select arrows were removed site-wide by a CSS shorthand → **fixed**.
- No custom 404/429/500 pages, no `robots.txt`, no sitemap, fixed `lang="fr"`, no `hreflang` → **fixed** (sitemap includes FR/EN alternates).
- Comment fields without labels, clickable `div`s not reachable by keyboard, no skip link, no reduced-motion support → **fixed**.
- Dashboard loaded every work four times just to build the filter lists; region filtering happened in Python; every public page ran four admin `COUNT` queries → **fixed** (SQL `DISTINCT`, SQL filters, counters only in /admin).
- Footer year hard-coded to 2024 → dynamic.
- No automated tests → **57 tests added**.
- Not changed on purpose: the personal text of *Notre Histoire* (e.g. "je lui avait demandé", and Jack's quoted words) is left exactly as written; correct it if you wish.

---

## 3. What was added

### 3.1 Bilingual site (French / English)
- Flask-Babel; **775 interface strings** translated (100%), including the admin area, form errors, flash messages, charts, map, PDF report, CSV headers and the full *Our Story* page.
- Language chosen from `?lang=fr|en`, remembered in the session, defaulting to the browser's `Accept-Language`. FR/EN switch in the navbar, `hreflang` alternates, `<html lang>` set per page.
- Stored values (regions, genres, languages, types, statuses) are translated at display time — the database is unchanged.
- **Bilingual content**: artists get `biographie_en`, works get `description_en`. English visitors see the English text when it exists, otherwise the French text with a "Text available in French only" notice (and the right `lang` attribute for screen readers). Demo entries now ship with English texts.

### 3.2 Security
Everything in §2, plus:
- **Two-factor authentication (TOTP)** for admins: QR code (rendered as inline SVG, no external service), replay protection, 8 single-use backup codes.
- **Account security page**: change password (12+ characters, 3 character classes, not common), enable/disable 2FA, regenerate backup codes, recent login attempts.
- **Audit log** (`/admin/journal`): every admin action — who, what, when, and a before → after diff of each changed field.
- Recovery commands: `flask admin-create`, `flask admin-reset-password`, `flask admin-disable-2fa`.

### 3.3 Admin editing of contributions
- Every field of an artist or work is editable, with server-side validation: photo (https only), official site, English bio / description, YouTube link (preview shown), and **reassigning a work to another artist** (e.g. contributor typo).
- **"Save and publish"** in one step.
- **"Original contribution" panel**: what the contributor actually sent, with each field the admin corrected flagged.
- **Change history** on each artist / work page.
- **Merge duplicates**: moves works, likes (without double counting), comments and reports to the right profile, then deletes the duplicate. Probable duplicates (same name) are pointed out automatically.
- "Fix the entry" button on each error report, bulk actions that respect the incomplete-profile rule, and a "profiles to complete" queue on the dashboard.

---

## 4. How it was verified

- **57 automated tests** (`pytest`): headers and CSP, every inline `<script>` nonced or inert, no `on*=` handler in any template, CSRF on forms / likes / admin actions, the XSS payloads above, URL validation, CSV injection, login lockout, open redirect, session invalidation, full 2FA flow including backup codes and the RFC 6238 test vector, rate limiting, honeypot, production config guards, the incomplete-artist workflow, field-level audit diffs, reassignment, duplicate merge, seed safety, and the i18n behaviour (including a check that the catalogue is 100% translated).
- **End-to-end in Chromium** (Playwright): 28 page loads (FR + EN) with zero console errors and zero CSP violations; CDN files served with their real bytes so the SRI hashes are proven; 24 Plotly charts render under the strict CSP; likes, search suggestions, YouTube player, map, language switch, comments, submission → admin edit → "save & publish" → public visibility; and **cancelling a delete no longer deletes**.
- **PostgreSQL 16**: the original code's deploy failure reproduced; then the new build steps run against that same old-schema database in production mode: migration OK, seed idempotent, existing like preserved, all pages 200, HSTS and secure cookies present.

---

## 5. What you need to do when deploying

1. **Environment variables on Render** (already in `render.yaml`; if the service was created by hand in the dashboard rather than from the Blueprint, add them manually):
   - `SECRET_KEY` (required, ≥ 32 random characters — production refuses to start without it)
   - `IP_HASH_SALT` (random), `TRUSTED_PROXIES=1`
   - `ADMIN_PASSWORD` is only used if no admin exists yet.
2. After the deploy, **log in, change the admin password, then enable 2FA** (Account security). Keep the backup codes somewhere safe.
3. Expected one-time effects: admins must log in again (session format changed); because visitor hashes are now salted, a visitor who had already liked something could like it once more (existing likes are kept).
4. Lost phone / locked out: open a Render shell and run `flask admin-disable-2fa admin` or `flask admin-reset-password admin`.

---

## 6. Recommended next steps (not done here)

- **Backups**: Render's free PostgreSQL plan has a limited lifetime and no backups — check your plan's expiry and export the data regularly (the admin CSV export helps, but a `pg_dump` is better).
- Self-host Bootstrap, the icon font and the Google Fonts, to remove third-party requests entirely (this would also let the CSP drop the external hosts).
- Move rate limiting to a shared store (e.g. Redis) if you scale beyond one instance — limits are currently per worker process (login lockout is already database-backed).
- Error monitoring (e.g. Sentry) and email notifications for new contributions.
- Several admin accounts with roles (moderator vs. administrator).
- A French translation catalogue would make plural forms for `0` follow French grammar ("0 œuvre" rather than "0 œuvres").
