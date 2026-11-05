"""Édition des contributions par l'admin : formulaires, approbation, historique, fusion."""
import json

from models import db, Artiste, Oeuvre, AuditLog, Like


def submit_work(client, **extra):
    data = {'titre': 'Ndolo', 'artiste_nom': 'Inconnu Total', 'type_oeuvre': 'Chanson',
            'genre_musical': 'Bikutsi', 'langue': 'Ewondo', 'annee_sortie': '1985',
            'soumis_par': 'Aline'}
    data.update(extra)
    return client.post('/collecte/oeuvre', data=data)


def test_submission_keeps_original_snapshot(client, app):
    assert submit_work(client).status_code == 302
    with app.app_context():
        o = Oeuvre.query.filter_by(titre='Ndolo').one()
        assert o.soumission_originale['titre'] == 'Ndolo'
        assert o.artiste.profil_incomplet is True


def test_known_artist_is_matched_case_insensitively(client, app):
    submit_work(client, artiste_nom='manu dibango')
    with app.app_context():
        assert Artiste.query.count() == 1
        assert Oeuvre.query.filter_by(titre='Ndolo').one().artiste_id == 1


def test_incomplete_artist_blocks_publication_until_completed(client, admin_client, app):
    submit_work(client)
    with app.app_context():
        o = Oeuvre.query.filter_by(titre='Ndolo').one()
        oid, aid = o.id, o.artiste_id

    admin_client.post(f'/admin/oeuvre/{oid}/action/approuver')
    with app.app_context():
        assert db.session.get(Oeuvre, oid).statut == 'approuve'
        assert db.session.get(Artiste, aid).statut == 'en_attente'    # pas d'auto-publication
    assert client.get(f'/explorer/oeuvre/{oid}').status_code == 404    # invisible au public

    admin_client.post(f'/admin/artiste/{aid}/action/approuver')        # refusé : incomplet
    with app.app_context():
        assert db.session.get(Artiste, aid).statut == 'en_attente'

    r = admin_client.post(f'/admin/artiste/{aid}/edit', data={
        'nom': 'Inconnu Total', 'region_origine': 'Sud', 'type_artiste': 'Groupe',
        'biographie_en': 'An English bio.', 'submit_action': 'save_approve'})
    assert r.status_code == 302
    with app.app_context():
        a = db.session.get(Artiste, aid)
        assert (a.statut, a.profil_incomplet, a.region_origine) == ('approuve', False, 'Sud')
    assert client.get(f'/explorer/oeuvre/{oid}').status_code == 200
    assert b'An English bio.' in client.get(f'/explorer/artiste/{aid}?lang=en').data


def test_edit_work_records_field_level_diff(admin_client, app):
    r = admin_client.post('/admin/oeuvre/1/edit', data={
        'titre': 'Soul Makossa (1972)', 'artiste_id': '1', 'type_oeuvre': 'Chanson',
        'genre_musical': 'Makossa', 'langue': 'Duala', 'annee_sortie': '1972',
        'description_en': 'The most sampled African song.', 'lien_youtube': 'https://youtu.be/PblSmVR7hCk'})
    assert r.status_code == 302
    with app.app_context():
        entry = AuditLog.query.filter_by(action='modification', cible_type='oeuvre').one()
        d = entry.details_dict
        assert d['titre'] == ['Soul Makossa', 'Soul Makossa (1972)']
        assert d['description_en'] == [None, 'The most sampled African song.']
        assert entry.admin_username == 'admin'
    page = admin_client.get('/admin/oeuvre/1').data.decode()
    assert 'Soul Makossa (1972)' in page and 'diff-new' in page


def test_reassign_work_to_another_artist(admin_client, app):
    with app.app_context():
        b = Artiste(nom='Richard Bona', region_origine='Est', type_artiste='Soliste_H', statut='approuve')
        db.session.add(b); db.session.commit(); bid = b.id
    admin_client.post('/admin/oeuvre/1/edit', data={
        'titre': 'Soul Makossa', 'artiste_id': str(bid), 'type_oeuvre': 'Chanson',
        'genre_musical': 'Makossa', 'langue': 'Duala', 'annee_sortie': '1972'})
    with app.app_context():
        assert db.session.get(Oeuvre, 1).artiste_id == bid
        d = AuditLog.query.filter_by(action='modification').one().details_dict
        assert d['artiste_id'] == ['Manu Dibango', 'Richard Bona']


def test_merge_duplicate_artists(admin_client, app):
    with app.app_context():
        dup = Artiste(nom='manu dibango', region_origine='Centre', type_artiste='Soliste_H',
                      statut='en_attente', site_web='https://manudibango.example')
        db.session.add(dup); db.session.flush()
        db.session.add(Oeuvre(titre='Tek Time', artiste_id=dup.id, genre_musical='Makossa',
                              langue='Français', annee_sortie=1975, statut='approuve'))
        db.session.add(Like(artiste_id=dup.id, ip_hash='abc'))
        db.session.add(Like(artiste_id=1, ip_hash='abc'))      # même visiteur : doublon de like
        db.session.commit(); dup_id = dup.id
    page = admin_client.get(f'/admin/artiste/{dup_id}').data.decode()
    assert 'Doublon probable' in page or 'Likely duplicate' in page
    r = admin_client.post(f'/admin/artiste/{dup_id}/fusionner', data={'cible_id': '1'})
    assert r.headers['Location'].endswith('/admin/artiste/1')
    with app.app_context():
        assert db.session.get(Artiste, dup_id) is None
        main = db.session.get(Artiste, 1)
        assert {o.titre for o in main.oeuvres} == {'Soul Makossa', 'Tek Time'}
        assert main.site_web == 'https://manudibango.example'
        assert Like.query.filter_by(artiste_id=1).count() == 1


def test_bulk_approve_skips_incomplete_artists(client, admin_client, app):
    submit_work(client)
    with app.app_context():
        aid = Oeuvre.query.filter_by(titre='Ndolo').one().artiste_id
    admin_client.post('/admin/bulk', data={'action': 'approuver', 'model': 'artiste', 'ids': [str(aid)]})
    with app.app_context():
        assert db.session.get(Artiste, aid).statut == 'en_attente'


def test_cancelled_delete_has_no_side_effect_by_design(admin_client, app):
    # La suppression n'est possible que par un POST explicite : un lien suivi
    # (ou une confirmation annulée qui naviguait quand même) ne supprime plus rien.
    admin_client.get('/admin/oeuvre/1/action/supprimer')
    with app.app_context():
        assert db.session.get(Oeuvre, 1) is not None
    admin_client.post('/admin/oeuvre/1/action/supprimer')
    with app.app_context():
        assert db.session.get(Oeuvre, 1) is None
        assert AuditLog.query.filter_by(action='suppression').count() == 1


def test_seed_never_overwrites_admin_edits(app):
    import seed_data
    with app.app_context():
        seed_data.seed()
        a = Artiste.query.filter_by(nom='Manu Dibango').one()
        a.biographie = 'Corrigée par un admin.'
        db.session.commit()
        seed_data.seed()
        a = Artiste.query.filter_by(nom='Manu Dibango').one()
        assert a.biographie == 'Corrigée par un admin.'
        assert a.biographie_en          # champ vide complété
        assert Oeuvre.query.filter_by(titre='Soul Makossa').count() == 1


def test_saving_unchanged_form_records_no_diff(admin_client, app):
    admin_client.post('/admin/oeuvre/1/edit', data={
        'titre': 'Soul Makossa', 'artiste_id': '1', 'type_oeuvre': 'Chanson', 'genre_musical': 'Makossa',
        'langue': 'Duala', 'annee_sortie': '1972', 'popularite': '',
        'lien_youtube': 'https://www.youtube.com/watch?v=PblSmVR7hCk'})
    with app.app_context():
        assert AuditLog.query.filter_by(action='modification').count() == 0


def test_history_shows_translated_status(admin_client):
    admin_client.post('/admin/oeuvre/1/action/rejeter')
    html = admin_client.get('/admin/oeuvre/1?lang=en').data.decode()
    assert 'Approved' in html and 'Rejected' in html and 'approuve</span>' not in html
