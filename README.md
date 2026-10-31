# Jackbeat

Bilingual (French / English) archive of Cameroonian musical heritage since 1960:
public contributions, admin moderation, public exploration with YouTube
playback, and a descriptive-analytics dashboard (charts, map, timeline, PDF/CSV).

See [`docs/EVALUATION.md`](docs/EVALUATION.md) for the security review and the
list of improvements.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pybabel compile -d translations
python seed_data.py            # demo data (insert-only)
python app.py                  # http://127.0.0.1:5000  — admin / jackbeat2024 (dev only)
pytest                         # test suite
```

## Configuration (environment variables)

| Variable | Required in production | Purpose |
|---|---|---|
| `FLASK_ENV` | yes (`production`) | `development` · `testing` · `production` |
| `SECRET_KEY` | **yes** (≥ 32 random chars) | Signs sessions; production refuses to start without it |
| `DATABASE_URL` | yes | PostgreSQL URL (`postgres://…` accepted) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | first deploy only | Creates the first admin if none exists (strong password required) |
| `IP_HASH_SALT` | recommended | Key used to anonymise visitor IPs |
| `TRUSTED_PROXIES` | yes on Render (`1`) | Number of reverse proxies in front of the app |

## Admin account commands

```bash
flask admin-create <username>           # prompts for a password
flask admin-reset-password <username>   # also logs out every session
flask admin-disable-2fa <username>      # lost phone
flask seed [--sync]                     # demo data; --sync updates demo rows in place
```

## Translations

Interface text is written in French in the code and translated in
`translations/en/LC_MESSAGES/messages.po`.

```bash
pybabel extract -F babel.cfg -k _l -o messages.pot .
pybabel update -i messages.pot -d translations
# edit translations/en/LC_MESSAGES/messages.po, then:
pybabel compile -d translations
```

Artist biographies and work descriptions have separate English fields, editable
by admins.
