"""
security.py — Boîte à outils sécurité de Jackbeat.

- En-têtes HTTP (CSP à nonce, HSTS, anti-clickjacking, etc.)
- Anonymisation des IP (HMAC salé, non réversible)
- Limitation de débit (rate limiting) par IP
- Redirections sûres (anti open-redirect)
- TOTP (RFC 6238) pour la double authentification + codes de secours
- Politique de mots de passe, validation d'URL, neutralisation des injections CSV
"""
import base64
import hashlib
import hmac
import json
import secrets
import struct
import threading
import time
from collections import defaultdict, deque
from functools import wraps
from urllib.parse import urlparse, urljoin

from flask import current_app, g, request, abort
from werkzeug.security import generate_password_hash, check_password_hash


# ════════════════════════════════════════════════
#  EN-TÊTES DE SÉCURITÉ + CONTENT SECURITY POLICY
# ════════════════════════════════════════════════

CDN_SCRIPTS = 'https://cdn.jsdelivr.net'
CDN_STYLES = 'https://cdn.jsdelivr.net https://fonts.googleapis.com'
CDN_FONTS = 'https://cdn.jsdelivr.net https://fonts.gstatic.com'


def csp_nonce():
    if not hasattr(g, 'csp_nonce'):
        g.csp_nonce = secrets.token_urlsafe(18)
    return g.csp_nonce


def build_csp(nonce):
    directives = [
        "default-src 'self'",
        # Aucun script inline sans nonce, aucun gestionnaire on*= dans le HTML
        f"script-src 'self' 'nonce-{nonce}' {CDN_SCRIPTS}",
        "script-src-attr 'none'",
        # Les attributs style="" restent autorisés (sans risque d'exécution de code)
        f"style-src 'self' 'unsafe-inline' {CDN_STYLES}",
        f"font-src 'self' data: {CDN_FONTS}",
        "img-src 'self' data: https:",
        "frame-src https://www.youtube-nocookie.com",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    if current_app.config.get('SESSION_COOKIE_SECURE'):
        directives.append('upgrade-insecure-requests')
    return '; '.join(directives)


def apply_security_headers(response):
    h = response.headers
    h['Content-Security-Policy'] = build_csp(csp_nonce())
    h['X-Content-Type-Options'] = 'nosniff'
    h['X-Frame-Options'] = 'DENY'
    h['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    h['Permissions-Policy'] = ('camera=(), microphone=(), geolocation=(), payment=(), '
                               'usb=(), interest-cohort=()')
    h['Cross-Origin-Opener-Policy'] = 'same-origin'
    if current_app.config.get('SESSION_COOKIE_SECURE'):
        h['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains'
    # Les pages admin et les réponses personnalisées ne doivent jamais être mises en cache
    if request.path.startswith('/admin'):
        h['Cache-Control'] = 'no-store, max-age=0'
        h['X-Robots-Tag'] = 'noindex, nofollow'
    return response


# ════════════════════════════════════════════════
#  IP, REDIRECTIONS
# ════════════════════════════════════════════════

def client_ip():
    # Grâce à ProxyFix (activé en production), remote_addr est l'IP réelle
    # transmise par le proxy de confiance — et non un X-Forwarded-For falsifiable.
    return request.remote_addr or '0.0.0.0'


def ip_hash(ip=None):
    """HMAC-SHA256 de l'IP : impossible de retrouver l'IP sans la clé serveur."""
    key = (current_app.config.get('IP_HASH_SALT') or current_app.config['SECRET_KEY']).encode()
    return hmac.new(key, (ip or client_ip()).encode(), hashlib.sha256).hexdigest()


def is_safe_redirect(target):
    if not target:
        return False
    target = target.strip()
    if target.startswith('//') or '\\' in target:
        return False
    host_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and test_url.netloc == host_url.netloc


def safe_redirect_target(*candidates, default='/'):
    for c in candidates:
        if is_safe_redirect(c):
            return c
    return default


# ════════════════════════════════════════════════
#  LIMITATION DE DÉBIT
# ════════════════════════════════════════════════

class RateLimiter:
    """Fenêtre glissante en mémoire, thread-safe (par processus)."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key, limit, period):
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - period:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            if len(self._hits) > 50000:   # garde-fou mémoire
                self._hits.clear()
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def rate_limit(limit, period, scope=None, methods=('POST',)):
    """Décorateur : `limit` requêtes par `period` secondes et par IP."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if (current_app.config.get('RATELIMIT_ENABLED', True)
                    and request.method in methods):
                key = f'{scope or f.__name__}:{ip_hash()}'
                if not limiter.hit(key, limit, period):
                    abort(429)
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ════════════════════════════════════════════════
#  TOTP (double authentification) — RFC 6238
# ════════════════════════════════════════════════

TOTP_PERIOD = 30
TOTP_DIGITS = 6


def totp_generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def _hotp(secret, counter):
    key = base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** TOTP_DIGITS)
    return str(code).zfill(TOTP_DIGITS)


def totp_code(secret, at=None):
    return _hotp(secret, int((at or time.time()) // TOTP_PERIOD))


def totp_verify(secret, code, last_step=None, window=1, at=None):
    """Renvoie le pas de temps validé (à mémoriser contre le rejeu) ou None."""
    code = (code or '').replace(' ', '').strip()
    if not secret or not code.isdigit() or len(code) != TOTP_DIGITS:
        return None
    current = int((at or time.time()) // TOTP_PERIOD)
    for step in range(current - window, current + window + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None


def totp_uri(secret, username, issuer='Jackbeat'):
    from urllib.parse import quote
    return (f'otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}'
            f'&issuer={quote(issuer)}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD}')


def totp_qr_svg(uri):
    """QR code SVG (aucune ressource externe — compatible CSP)."""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return None
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    svg = img.to_string(encoding='unicode')
    return svg


def generate_backup_codes(n=8):
    codes = ['-'.join([secrets.token_hex(2), secrets.token_hex(2)]) for _ in range(n)]
    hashes = [generate_password_hash(c, method='pbkdf2:sha256:200000') for c in codes]
    return codes, json.dumps(hashes)


def consume_backup_code(stored_json, code):
    """Vérifie un code de secours ; renvoie le nouveau JSON (code consommé) ou None."""
    code = (code or '').strip().lower()
    if not stored_json or not code:
        return None
    hashes = json.loads(stored_json)
    for i, h in enumerate(hashes):
        if check_password_hash(h, code):
            del hashes[i]
            return json.dumps(hashes)
    return None


# ════════════════════════════════════════════════
#  MOTS DE PASSE
# ════════════════════════════════════════════════

COMMON_PASSWORDS = {
    'password', 'motdepasse', 'azerty', 'qwerty', '123456', '12345678', '123456789',
    'admin', 'administrator', 'jackbeat', 'jackbeat2024', 'cameroun', 'letmein',
    'welcome', 'iloveyou', 'password1', 'azertyuiop', 'qwertyuiop',
}
PASSWORD_MIN_LENGTH = 12


def password_problems(password, username=''):
    """Liste (vide = OK) des règles non respectées. Messages traduits par l'appelant."""
    from flask_babel import gettext as _
    problems = []
    if len(password or '') < PASSWORD_MIN_LENGTH:
        problems.append(_('Au moins %(n)d caractères.', n=PASSWORD_MIN_LENGTH))
    classes = sum([any(c.islower() for c in password), any(c.isupper() for c in password),
                   any(c.isdigit() for c in password), any(not c.isalnum() for c in password)])
    if classes < 3:
        problems.append(_('Au moins 3 types de caractères parmi : minuscules, majuscules, chiffres, symboles.'))
    low = (password or '').lower()
    if low in COMMON_PASSWORDS or any(w in low for w in ('jackbeat', 'password', 'motdepasse')):
        problems.append(_('Mot de passe trop courant.'))
    if username and username.lower() in low:
        problems.append(_("Ne doit pas contenir l'identifiant."))
    return problems


# ════════════════════════════════════════════════
#  VALIDATION / NEUTRALISATION
# ════════════════════════════════════════════════

def is_http_url(url, https_only=False):
    """N'accepte que http(s)://hôte — bloque javascript:, data:, etc."""
    if not url:
        return False
    try:
        p = urlparse(url.strip())
    except ValueError:
        return False
    schemes = ('https',) if https_only else ('http', 'https')
    return p.scheme in schemes and bool(p.netloc) and ' ' not in url.strip()


CSV_DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def csv_safe(value):
    """Empêche l'injection de formules dans Excel / LibreOffice (CSV injection)."""
    if value is None:
        return ''
    s = str(value)
    if s.startswith(CSV_DANGEROUS_PREFIXES):
        return "'" + s
    return s
