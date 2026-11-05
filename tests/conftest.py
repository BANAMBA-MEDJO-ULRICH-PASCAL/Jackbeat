import os
import re
import sys

import pytest

os.environ['FLASK_ENV'] = 'testing'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                      # noqa: E402
from models import db, Artiste, Oeuvre, Admin  # noqa: E402
from security import limiter                    # noqa: E402

ADMIN_PASSWORD = 'Test-Admin-Pass-2026!'


@pytest.fixture
def app():
    application = create_app('testing')
    limiter.reset()
    with application.app_context():
        artiste = Artiste(nom='Manu Dibango', region_origine='Littoral', type_artiste='Soliste_H',
                          statut='approuve', biographie='Légende du Makossa.')
        db.session.add(artiste)
        db.session.flush()
        db.session.add(Oeuvre(titre='Soul Makossa', artiste_id=artiste.id, genre_musical='Makossa',
                              langue='Duala', annee_sortie=1972, statut='approuve',
                              lien_youtube='https://www.youtube.com/watch?v=PblSmVR7hCk'))
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username='admin', password=ADMIN_PASSWORD):
    return client.post('/admin/login', data={'username': username, 'password': password})


@pytest.fixture
def admin_client(client):
    r = login(client)
    assert r.status_code == 302 and r.headers['Location'].endswith('/admin/')
    return client


@pytest.fixture
def csrf_app(app):
    app.config['WTF_CSRF_ENABLED'] = True
    return app


def csrf_token_from(html):
    m = re.search(r'name="csrf_token" (?:type="hidden" )?value="([^"]+)"', html) or \
        re.search(r'name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None
