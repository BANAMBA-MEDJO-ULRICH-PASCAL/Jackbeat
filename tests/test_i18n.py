"""Bilinguisme FR / EN."""
import re


def lang_of(html):
    return re.search(r'<html lang="(\w+)"', html).group(1)


def test_default_is_french(client):
    html = client.get('/').data.decode()
    assert lang_of(html) == 'fr'
    assert 'Accueil' in html and 'Contribuer' in html


def test_accept_language_english(client):
    html = client.get('/', headers={'Accept-Language': 'en-US,en;q=0.9'}).data.decode()
    assert lang_of(html) == 'en' and 'Contribute' in html


def test_lang_param_switches_and_persists(client):
    html = client.get('/?lang=en').data.decode()
    assert lang_of(html) == 'en'
    assert 'Our Story' in html and 'Cameroonian Musical Heritage' in html
    html = client.get('/explorer/artistes').data.decode()           # pas de paramètre
    assert lang_of(html) == 'en' and 'Region:' in html
    assert lang_of(client.get('/?lang=fr').data.decode()) == 'fr'


def test_invalid_lang_is_ignored(client):
    assert lang_of(client.get('/?lang=xx').data.decode()) == 'fr'


def test_hreflang_alternates(client):
    html = client.get('/explorer/artistes?lang=en').data.decode()
    assert 'hreflang="fr"' in html and 'hreflang="en"' in html


def test_data_labels_are_translated(client):
    html = client.get('/explorer/artiste/1?lang=en').data.decode()
    assert 'Solo artist (Male)' in html
    html = client.get('/dashboard/carte?lang=en').data.decode()
    assert 'Far North' in html and 'South-West' in html


def test_french_only_content_is_flagged_in_english(client):
    html = client.get('/explorer/artiste/1?lang=en').data.decode()
    assert 'Text available in French only' in html
    assert 'lang="fr"' in html


def test_story_page_translated(client):
    html = client.get('/notre-histoire?lang=en').data.decode()
    assert 'For Jack' in html and 'little brother' in html


def test_admin_is_bilingual(admin_client):
    html = admin_client.get('/admin/?lang=en').data.decode()
    assert 'Dashboard' in html and 'Audit log' in html


def test_pdf_report_in_both_languages(client):
    for lang in ('fr', 'en'):
        r = client.get(f'/dashboard/export/rapport.pdf?lang={lang}')
        assert r.status_code == 200 and r.data.startswith(b'%PDF')


def test_all_catalog_entries_translated():
    from babel.messages.pofile import read_po
    import pathlib
    po = pathlib.Path(__file__).resolve().parent.parent / 'translations/en/LC_MESSAGES/messages.po'
    cat = read_po(po.open('rb'))
    missing = [m.id for m in cat if m.id and not (all(m.string) if isinstance(m.string, tuple) else m.string)]
    assert missing == []
