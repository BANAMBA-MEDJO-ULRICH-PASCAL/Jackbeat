"""Tests de sécurité : en-têtes, CSRF, XSS, authentification, 2FA, limitation de débit."""
import pathlib
import re
import time

import pytest

from conftest import login, csrf_token_from, ADMIN_PASSWORD
from models import db, Artiste, Oeuvre, Admin, Commentaire, AuditLog
from security import totp_code, totp_verify, limiter, csv_safe, is_http_url, password_problems

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── En-têtes & CSP ──────────────────────────────────────────

def test_security_headers_present(client):
    r = client.get('/')
    h = r.headers
    assert h['X-Frame-Options'] == 'DENY'
    assert h['X-Content-Type-Options'] == 'nosniff'
    assert 'strict-origin' in h['Referrer-Policy']
    csp = h['Content-Security-Policy']
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "script-src-attr 'none'" in csp
    assert "'unsafe-eval'" not in csp
    assert re.search(r"script-src 'self' 'nonce-[\w-]+'", csp)


def test_every_inline_script_is_inert_or_nonced(client):
    for url in ['/', '/explorer/artiste/1', '/dashboard/', '/dashboard/carte', '/dashboard/chronologie']:
        r = client.get(url)
        nonce = re.search(r"'nonce-([\w-]+)'", r.headers['Content-Security-Policy']).group(1)
        for tag in re.findall(r'<script\b[^>]*>', r.data.decode()):
            if 'src=' in tag:
                assert 'integrity=' in tag or 'src="/static/' in tag, f'{url}: CDN script without SRI: {tag}'
                continue
            assert 'type="application/json"' in tag or f'nonce="{nonce}"' in tag, f'{url}: {tag}'


def test_no_inline_event_handlers_in_templates():
    pattern = re.compile(r'\son[a-z]+\s*=\s*["\']', re.I)
    offenders = [str(p.relative_to(ROOT)) for p in (ROOT / 'templates').rglob('*.html')
                 if pattern.search(p.read_text(encoding='utf-8'))]
    assert offenders == []


def test_admin_pages_not_cached(admin_client):
    r = admin_client.get('/admin/')
    assert 'no-store' in r.headers['Cache-Control']


# ── CSRF ────────────────────────────────────────────────────

def test_comment_without_csrf_token_is_rejected(csrf_app):
    c = csrf_app.test_client()
    r = c.post('/explorer/commenter/oeuvre/1', data={'auteur': 'Eve', 'texte': 'Spam spam spam'})
    assert r.status_code == 400
    with csrf_app.app_context():
        assert Commentaire.query.count() == 0


def test_comment_with_csrf_token_is_accepted(csrf_app):
    c = csrf_app.test_client()
    token = csrf_token_from(c.get('/explorer/oeuvre/1').data.decode())
    r = c.post('/explorer/commenter/oeuvre/1', data={'auteur': 'Ada', 'texte': 'Un classique !', 'csrf_token': token})
    assert r.status_code == 302
    with csrf_app.app_context():
        assert Commentaire.query.count() == 1


def test_like_requires_csrf_header(csrf_app):
    c = csrf_app.test_client()
    assert c.post('/explorer/like/oeuvre/1').status_code == 400
    token = csrf_token_from(c.get('/explorer/oeuvre/1').data.decode())
    r = c.post('/explorer/like/oeuvre/1', headers={'X-CSRFToken': token, 'X-Requested-With': 'XMLHttpRequest'})
    assert r.status_code == 200 and r.json == {'liked': True, 'nb': 1}


def test_admin_state_changes_refuse_get(admin_client, app):
    # Avant : un simple lien (ou une image piégée) suffisait à supprimer un artiste.
    r = admin_client.get('/admin/artiste/1/action/supprimer')
    assert r.status_code == 405
    with app.app_context():
        assert db.session.get(Artiste, 1) is not None


def test_logout_requires_post(admin_client):
    assert admin_client.get('/admin/logout').status_code == 405


# ── XSS ─────────────────────────────────────────────────────

def test_malicious_title_never_reaches_a_js_context(app, client):
    payload = "x',document.title='XSS','"
    with app.app_context():
        db.session.add(Oeuvre(titre=payload, artiste_id=1, genre_musical='Makossa', langue='Duala',
                              annee_sortie=1980, statut='approuve',
                              lien_youtube='https://youtu.be/PblSmVR7hCk'))
        db.session.commit()
    html = client.get('/explorer/artiste/1').data.decode()
    assert 'onclick' not in html
    assert 'data-yt-title="x&#39;,document.title=&#39;XSS&#39;,&#39;"' in html


def test_javascript_url_rejected_for_youtube_link(client, app):
    r = client.post('/collecte/oeuvre', data={
        'titre': 'Piège', 'artiste_nom': 'Manu Dibango', 'type_oeuvre': 'Chanson',
        'genre_musical': 'Makossa', 'langue': 'Duala', 'annee_sortie': '1980',
        'lien_youtube': 'javascript:alert(document.cookie)'})
    assert r.status_code == 200          # formulaire ré-affiché avec erreur
    with app.app_context():
        assert Oeuvre.query.filter_by(titre='Piège').count() == 0


def test_admin_rejects_non_https_photo_url(admin_client, app):
    r = admin_client.post('/admin/artiste/1/edit', data={
        'nom': 'Manu Dibango', 'region_origine': 'Littoral', 'type_artiste': 'Soliste_H',
        'photo_url': 'javascript:alert(1)', 'site_web': 'data:text/html,hi'})
    assert r.status_code == 200
    with app.app_context():
        a = db.session.get(Artiste, 1)
        assert a.photo_url is None and a.site_web is None


@pytest.mark.parametrize('url,ok', [
    ('https://example.org/x.jpg', True), ('http://example.org', True),
    ('javascript:alert(1)', False), ('data:text/html,x', False), ('//evil.com', False), ('', False),
])
def test_is_http_url(url, ok):
    assert is_http_url(url) is ok


def test_csv_injection_neutralised(app, admin_client):
    with app.app_context():
        db.session.add(Oeuvre(titre='=HYPERLINK("http://evil","clic")', artiste_id=1, genre_musical='Jazz',
                              langue='Français', annee_sortie=1990, statut='approuve'))
        db.session.commit()
    for url in ('/admin/export/oeuvres.csv', '/dashboard/export/donnees.csv'):
        body = admin_client.get(url).data.decode('utf-8-sig')
        assert "'=HYPERLINK" in body
        assert '\n=HYPERLINK' not in body and ',=HYPERLINK' not in body
    assert csv_safe('+1') == "'+1" and csv_safe('Makossa') == 'Makossa'


def test_public_csv_has_no_personal_data(app, client):
    with app.app_context():
        o = db.session.get(Oeuvre, 1)
        o.soumis_par, o.soumis_email = 'Alice', 'alice@example.org'
        db.session.commit()
    body = client.get('/dashboard/export/donnees.csv').data.decode('utf-8-sig')
    assert 'alice@example.org' not in body and 'Alice' not in body


# ── Authentification ────────────────────────────────────────

def test_default_credentials_do_not_work(client):
    r = login(client, 'admin', 'jackbeat2024')
    assert r.status_code == 200
    assert b'/admin/logout' not in r.data


def test_login_lockout_after_repeated_failures(client, app):
    for _ in range(app.config['LOGIN_MAX_FAILS_PER_IP']):
        login(client, 'admin', 'wrong-password')
    r = login(client)                    # bon mot de passe, mais IP bloquée
    assert r.status_code == 200
    assert client.get('/admin/').status_code == 302


def test_open_redirect_blocked(client):
    r = client.post('/admin/login?next=https://evil.example/phish',
                    data={'username': 'admin', 'password': ADMIN_PASSWORD})
    assert r.headers['Location'] == '/admin/'
    client.post('/admin/logout')


def test_password_change_logs_out_other_sessions(app):
    a, b = app.test_client(), app.test_client()
    login(a); login(b)
    assert a.get('/admin/').status_code == 200
    r = b.post('/admin/securite/mot-de-passe', data={
        'current_password': ADMIN_PASSWORD, 'new_password': 'Nouvelle-Phrase-De-Passe-42',
        'confirm': 'Nouvelle-Phrase-De-Passe-42'})
    assert r.status_code == 302
    assert b.get('/admin/').status_code == 200        # session courante conservée
    assert a.get('/admin/').status_code == 302        # autre session invalidée


def test_weak_password_refused(admin_client, app):
    admin_client.post('/admin/securite/mot-de-passe', data={
        'current_password': ADMIN_PASSWORD, 'new_password': 'jackbeat2024', 'confirm': 'jackbeat2024'})
    with app.app_context():
        assert Admin.query.first().check_password(ADMIN_PASSWORD)
    assert password_problems('Correct-Horse-Battery-9') == []
    assert password_problems('short') != []


# ── Double authentification ─────────────────────────────────

def test_totp_rfc6238_vector():
    secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'   # "12345678901234567890"
    assert totp_code(secret, at=59) == '287082'
    assert totp_verify(secret, '287082', at=59) == 1
    assert totp_verify(secret, '287082', last_step=1, at=59) is None   # anti-rejeu


def test_full_2fa_flow(app):
    c = app.test_client()
    login(c)
    c.get('/admin/securite/2fa')
    with c.session_transaction() as s:
        secret = s['totp_setup']
    r = c.post('/admin/securite/2fa', data={'code': totp_code(secret)})
    assert r.status_code == 200 and b'-' in r.data             # codes de secours affichés
    codes = re.findall(r'>([0-9a-f]{4}-[0-9a-f]{4})<', r.data.decode())
    assert len(codes) == 8
    c.post('/admin/logout')

    # Mot de passe seul : insuffisant
    r = login(c)
    assert r.headers['Location'].endswith('/admin/login/verification')
    assert c.get('/admin/').status_code == 302
    assert c.post('/admin/login/verification', data={'code': '000000'}).status_code == 200
    assert c.get('/admin/').status_code == 302

    # Code de secours : fonctionne une seule fois
    r = c.post('/admin/login/verification', data={'code': codes[0]})
    assert r.status_code == 302 and c.get('/admin/').status_code == 200
    c.post('/admin/logout')
    login(c)
    assert c.post('/admin/login/verification', data={'code': codes[0]}).status_code == 200
    assert c.get('/admin/').status_code == 302


# ── Abus ────────────────────────────────────────────────────

def test_rate_limit_on_comments(app, client):
    app.config['RATELIMIT_ENABLED'] = True
    limiter.reset()
    codes = [client.post('/explorer/commenter/artiste/1', data={'auteur': 'Bob', 'texte': f'Message {i} ok'}).status_code
             for i in range(7)]
    assert codes[:5] == [302] * 5 and codes[-1] == 429


def test_honeypot_silently_discards_bots(client, app):
    r = client.post('/collecte/artiste', data={'nom': 'Robot', 'region_origine': 'Centre',
                                               'type_artiste': 'Groupe', 'website': 'http://spam'})
    assert r.status_code == 302
    with app.app_context():
        assert Artiste.query.filter_by(nom='Robot').count() == 0


def test_view_counter_counts_once_per_visitor(client, app):
    for _ in range(5):
        client.get('/explorer/oeuvre/1')
    with app.app_context():
        assert db.session.get(Oeuvre, 1).nb_vues == 1


# ── Configuration ───────────────────────────────────────────

def test_production_refuses_missing_secret_key(monkeypatch):
    from app import create_app
    monkeypatch.delenv('SECRET_KEY', raising=False)
    with pytest.raises(RuntimeError):
        create_app('production')


def test_production_accepts_a_strong_secret_key(monkeypatch, tmp_path):
    from app import create_app
    import config
    monkeypatch.setenv('SECRET_KEY', 'k' * 48)
    monkeypatch.setattr(config.ProductionConfig, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{tmp_path}/ok.db')
    app = create_app('production')
    assert app.config['SECRET_KEY'] == 'k' * 48
    assert app.config['SESSION_COOKIE_SECURE'] is True


def test_production_refuses_the_dev_secret_key(monkeypatch):
    from app import create_app
    from config import DEV_SECRET_KEY
    monkeypatch.setenv('SECRET_KEY', DEV_SECRET_KEY)
    with pytest.raises(RuntimeError):
        create_app('production')


def test_postgres_url_uses_installed_driver(monkeypatch):
    from config import _db_url
    monkeypatch.setenv('DATABASE_URL', 'postgres://u:p@h:5432/db')
    assert _db_url('x') == 'postgresql+psycopg2://u:p@h:5432/db'


def test_production_does_not_create_admin_with_weak_password(monkeypatch, tmp_path):
    from app import create_app
    import config
    monkeypatch.setenv('SECRET_KEY', 'x' * 48)
    monkeypatch.setattr(config.ProductionConfig, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{tmp_path}/p.db')
    monkeypatch.setattr(config.ProductionConfig, 'ADMIN_PASSWORD', 'jackbeat2024')
    app = create_app('production')
    with app.app_context():
        assert Admin.query.count() == 0
