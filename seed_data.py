"""
seed_data.py — Données de démonstration VÉRIFIÉES.
"""
import os
import sys

from models import db, Artiste, Oeuvre

SAMPLE_DATA = [
    {
        'artiste': {
            'nom':'Manu Dibango', 'region_origine':'Littoral', 'type_artiste':'Soliste_H',
            'annee_debut':1960, 'annee_fin':2020, 'statut':'approuve',
            'biographie':'Légende mondiale du Makossa, saxophoniste et pianiste. Son titre Soul Makossa (1972) a influencé Michael Jackson et Rihanna.',
            'biographie_en':'World-famous Makossa legend, saxophonist and pianist. His song Soul Makossa (1972) influenced Michael Jackson and Rihanna.',
        },
        'oeuvres': [
            {'titre':'Soul Makossa','type_oeuvre':'Chanson','genre_musical':'Makossa',
             'langue':'Duala','annee_sortie':1972,'popularite':'Internationale',
             'distinction':'Chanson africaine la plus samplée de l\'histoire',
             'lien_youtube':'https://www.youtube.com/watch?v=PblSmVR7hCk',
             'description':'Titre emblématique du Makossa, samplé par de nombreux artistes internationaux dont Michael Jackson et Rihanna.',
             'description_en':'The signature Makossa track, sampled by many international artists including Michael Jackson and Rihanna.'},
        ]
    },
    {
        'artiste': {
            'nom':'Charlotte Dipanda', 'region_origine':'Centre', 'type_artiste':'Soliste_F',
            'annee_debut':2002, 'statut':'approuve',
            'biographie':'Née à Yaoundé en 1985, voix incontournable de la musique acoustique camerounaise contemporaine.',
            'biographie_en':'Born in Yaoundé in 1985, a leading voice of contemporary Cameroonian acoustic music.',
        },
        'oeuvres': [
            {'titre':'Ndolo Bukatè','type_oeuvre':'Chanson','genre_musical':'Afrobeat',
             'langue':'Duala','annee_sortie':2015,'popularite':'Nationale',
             'lien_youtube':'https://www.youtube.com/watch?v=MPYGv033Rs8',
             'description':'Extrait de l\'album "Massa" (2015), chanté en langue Duala.',
             'description_en':'From the album "Massa" (2015), sung in Duala.'},
        ]
    },
    {
        'artiste': {
            'nom':'Anne-Marie Nzié', 'region_origine':'Littoral', 'type_artiste':'Soliste_F',
            'annee_debut':1955, 'annee_fin':2020, 'statut':'approuve',
            'biographie':'Pionnière de la musique camerounaise, surnommée "La grande dame de la chanson camerounaise".',
            'biographie_en':'A pioneer of Cameroonian music, nicknamed "the grande dame of Cameroonian song".',
        },
        'oeuvres': []
    },
    {
        'artiste': {
            'nom':'Koppo', 'region_origine':'Centre', 'type_artiste':'Soliste_H',
            'annee_debut':2003, 'statut':'approuve',
            'biographie':'Figure du Bikutsi moderne et de la scène musicale camerounaise du Centre.',
            'biographie_en':'A figure of modern Bikutsi and of the music scene of the Centre region.',
        },
        'oeuvres': []
    },
    {
        'artiste': {
            'nom':'Locko', 'region_origine':'Littoral', 'type_artiste':'Soliste_H',
            'annee_debut':2015, 'statut':'approuve',
            'biographie':'Artiste afropop de la nouvelle génération camerounaise.',
            'biographie_en':'Afropop artist from the new generation of Cameroonian musicians.',
        },
        'oeuvres': []
    },
    {
        'artiste': {
            'nom':'Les Têtes Brulées', 'region_origine':'Centre', 'type_artiste':'Groupe',
            'annee_debut':1985, 'annee_fin':1995, 'statut':'approuve',
            'biographie':'Groupe de Bikutsi révolutionnaire, connu pour leur look punk-africain. Leur guitariste Théodore "Zanzibar" Epeme imitait le son du balafon avec de la mousse sur les cordes.',
            'biographie_en':'A revolutionary Bikutsi band known for its punk-African look. Their guitarist Théodore "Zanzibar" Epeme imitated the sound of the balafon by placing foam on his guitar strings.',
        },
        'oeuvres': [
            {'titre':'Hot Heads','type_oeuvre':'Album','genre_musical':'Bikutsi',
             'langue':'Multilingue','annee_sortie':1990,'popularite':'Internationale',
             'distinction':'Tournée nord-américaine en 1990',
             'description':'Album emblématique du Bikutsi moderne, enregistré en France.',
             'description_en':'A landmark album of modern Bikutsi, recorded in France.',
             'lien_youtube': None},
        ]
    },
    {
        'artiste': {
            'nom':'Richard Bona', 'region_origine':'Est', 'type_artiste':'Soliste_H',
            'annee_debut':1990, 'statut':'approuve',
            'biographie':'Bassiste virtuose de renommée mondiale, originaire de Minta (Est-Cameroun), ambassadeur du jazz afro-fusion.',
            'biographie_en':'World-renowned virtuoso bassist from Minta (East Cameroon), an ambassador of Afro-fusion jazz.',
        },
        'oeuvres': [
            {'titre':'Munia (The Tale)','type_oeuvre':'Album','genre_musical':'Jazz',
             'langue':'Multilingue','annee_sortie':2003,'popularite':'Internationale',
             'description':'Troisième album studio de Richard Bona, sorti le 22 septembre 2003 chez Universal Music France.',
             'description_en':"Richard Bona's third studio album, released on 22 September 2003 by Universal Music France.",
             'lien_youtube': None},
        ]
    },
]


def _completer(obj, data, sync):
    """Remplit les champs vides (jamais d'écrasement), ou tout synchronise si sync=True."""
    change = False
    for key, value in data.items():
        if sync or getattr(obj, key) in (None, ''):
            if getattr(obj, key) != value:
                setattr(obj, key, value)
                change = True
    return int(change)


def seed(sync=False):
    """Insère les artistes / œuvres de démonstration manquants.

    Par défaut, seuls les champs VIDES des fiches existantes sont complétés
    (ex. biographie anglaise) : les corrections faites par l'admin, les likes,
    commentaires et vues sont préservés à chaque déploiement.
    Avec sync=True (ou SEED_SYNC=1), les fiches de démo existantes sont mises à
    jour EN PLACE (même identifiant) — sans jamais supprimer de ligne.
    """
    from flask import has_app_context
    if not has_app_context():
        from app import create_app
        with create_app().app_context():
            return seed(sync)

    ajouts, majs = 0, 0
    for entry in SAMPLE_DATA:
        data = entry['artiste']
        artiste = Artiste.query.filter(db.func.lower(Artiste.nom) == data['nom'].lower()).first()
        if artiste is None:
            artiste = Artiste(**data)
            db.session.add(artiste)
            db.session.flush()
            ajouts += 1
        else:
            majs += _completer(artiste, data, sync)

        for o in entry['oeuvres']:
            oeuvre = (Oeuvre.query.filter_by(artiste_id=artiste.id)
                      .filter(db.func.lower(Oeuvre.titre) == o['titre'].lower()).first())
            if oeuvre is None:
                db.session.add(Oeuvre(artiste_id=artiste.id, statut='approuve', **o))
                ajouts += 1
            else:
                majs += _completer(oeuvre, o, sync)

    db.session.commit()
    print(f"✅ Démo : {ajouts} ajout(s), {majs} mise(s) à jour · "
          f"{Artiste.query.count()} artistes · {Oeuvre.query.count()} œuvres en base.")


if __name__ == '__main__':
    seed(sync='--sync' in sys.argv or os.environ.get('SEED_SYNC') == '1')
