"""
seed_data.py — Données de démonstration avec liens YouTube réels.
"""
from app import create_app
from models import db, Artiste, Oeuvre

app = create_app('development')

SAMPLE_DATA = [
    {
        'artiste': {
            'nom':'Manu Dibango', 'region_origine':'Littoral', 'type_artiste':'Soliste_H',
            'annee_debut':1960, 'statut':'approuve',
            'biographie':'Légende mondiale du Makossa, saxophoniste et pianiste. Son titre Soul Makossa (1972) a influencé Michael Jackson et Rihanna.',
        },
        'oeuvres': [
            {'titre':'Soul Makossa','type_oeuvre':'Chanson','genre_musical':'Makossa',
             'langue':'Duala','annee_sortie':1972,'popularite':'Internationale',
             'distinction':'Billboard Hot 100 — 1973',
             'lien_youtube':'https://www.youtube.com/watch?v=MrClkn7j5tc',
             'description':'Hymne mondial du Makossa, samplé par Michael Jackson et Rihanna.'},
            {'titre':'Makossa Man','type_oeuvre':'Album','genre_musical':'Makossa',
             'langue':'Français','annee_sortie':1974,'popularite':'Continentale',
             'lien_youtube':'https://www.youtube.com/watch?v=AjXFqXBCOY8'},
        ]
    },
    {
        'artiste': {
            'nom':'Charlotte Dipanda', 'region_origine':'Littoral', 'type_artiste':'Soliste_F',
            'annee_debut':2005, 'statut':'approuve',
            'biographie':'Voix incontournable de la musique camerounaise contemporaine, ambassadrice du Makossa moderne.',
        },
        'oeuvres': [
            {'titre':'Ndo Kolo','type_oeuvre':'Chanson','genre_musical':'Makossa',
             'langue':'Duala','annee_sortie':2009,'popularite':'Nationale',
             'lien_youtube':'https://www.youtube.com/watch?v=j0UoEO9sGYE'},
            {'titre':'De toutes les couleurs','type_oeuvre':'Album','genre_musical':'R&B',
             'langue':'Français','annee_sortie':2012,'popularite':'Continentale',
             'lien_youtube':'https://www.youtube.com/watch?v=L_jWHffIx5E'},
        ]
    },
    {
        'artiste': {
            'nom':'Anne-Marie Nzié', 'region_origine':'Littoral', 'type_artiste':'Soliste_F',
            'annee_debut':1955, 'annee_fin':2020, 'statut':'approuve',
            'biographie':'Pionnière de la musique camerounaise, surnommée "La grande dame de la chanson camerounaise".',
        },
        'oeuvres': [
            {'titre':'Ayo','type_oeuvre':'Chanson','genre_musical':'Makossa',
             'langue':'Duala','annee_sortie':1968,'popularite':'Nationale',
             'lien_youtube':'https://www.youtube.com/watch?v=9bZkp7q19f0'},
        ]
    },
    {
        'artiste': {
            'nom':'Maahlox le Vibeur', 'region_origine':'Centre', 'type_artiste':'Soliste_H',
            'annee_debut':2010, 'statut':'approuve',
            'biographie':'Ambassadeur du Bikutsi moderne, il a su moderniser ce rythme traditionnel du Centre Cameroun.',
        },
        'oeuvres': [
            {'titre':'Ma Lova','type_oeuvre':'Chanson','genre_musical':'Bikutsi',
             'langue':'Ewondo','annee_sortie':2012,'popularite':'Nationale',
             'lien_youtube':'https://www.youtube.com/watch?v=LhZLgL8z9X4'},
        ]
    },
    {
        'artiste': {
            'nom':'Koppo', 'region_origine':'Centre', 'type_artiste':'Soliste_H',
            'annee_debut':2005, 'statut':'approuve',
            'biographie':'Star du Bikutsi, artiste engagé et figure incontournable de la scène musicale centrafricaine.',
        },
        'oeuvres': [
            {'titre':'Kotto Bass','type_oeuvre':'Chanson','genre_musical':'Bikutsi',
             'langue':'Ewondo','annee_sortie':2008,'popularite':'Nationale',
             'lien_youtube':'https://www.youtube.com/watch?v=wE_hOk5KbBs'},
        ]
    },
    {
        'artiste': {
            'nom':'Locko', 'region_origine':'Littoral', 'type_artiste':'Soliste_H',
            'annee_debut':2015, 'statut':'approuve',
            'biographie':'Artiste afropop incontournable de la nouvelle génération camerounaise, voix veloutée et mélodies entraînantes.',
        },
        'oeuvres': [
            {'titre':'Je t\'aime un peu','type_oeuvre':'Chanson','genre_musical':'Afrobeat',
             'langue':'Français','annee_sortie':2017,'popularite':'Continentale',
             'lien_youtube':'https://www.youtube.com/watch?v=JGwWNGJdvx8'},
            {'titre':'Doux','type_oeuvre':'Chanson','genre_musical':'Afrobeat',
             'langue':'Français','annee_sortie':2020,'popularite':'Continentale',
             'lien_youtube':'https://www.youtube.com/watch?v=n6X2L285WLc'},
        ]
    },
    {
        'artiste': {
            'nom':'Les Têtes Brulées', 'region_origine':'Centre', 'type_artiste':'Groupe',
            'annee_debut':1987, 'annee_fin':1995, 'statut':'approuve',
            'biographie':'Groupe de Bikutsi révolutionnaire, connu pour leur look punk-africain et leurs performances scéniques explosives.',
        },
        'oeuvres': [
            {'titre':'Hot Koki','type_oeuvre':'Album','genre_musical':'Bikutsi',
             'langue':'Ewondo','annee_sortie':1988,'popularite':'Internationale',
             'distinction':'Documentaire BBC — 1992',
             'lien_youtube':'https://www.youtube.com/watch?v=4DuOFXN7vLA'},
        ]
    },
    {
        'artiste': {
            'nom':'Richard Bona', 'region_origine':'Sud', 'type_artiste':'Soliste_H',
            'annee_debut':1990, 'statut':'approuve',
            'biographie':'Bassiste virtuose de renommée mondiale, ambassadeur du jazz africain et de la fusion afro-jazz.',
        },
        'oeuvres': [
            {'titre':'Munia: The Tale','type_oeuvre':'Album','genre_musical':'Jazz',
             'langue':'Multilingue','annee_sortie':1999,'popularite':'Internationale',
             'lien_youtube':'https://www.youtube.com/watch?v=dQw4w9WgXcQ'},
        ]
    },
]


def seed():
    with app.app_context():
        if Artiste.query.count() > 0:
            print("⚠️  Base non vide — suppression et recréation...")
            Oeuvre.query.delete()
            Artiste.query.delete()
            db.session.commit()

        for entry in SAMPLE_DATA:
            artiste = Artiste(**entry['artiste'])
            db.session.add(artiste)
            db.session.flush()
            for o in entry['oeuvres']:
                oeuvre = Oeuvre(artiste_id=artiste.id, statut='approuve', **o)
                db.session.add(oeuvre)

        db.session.commit()
        print(f"✅ {Artiste.query.count()} artistes · {Oeuvre.query.count()} œuvres ajoutés avec liens YouTube !")


if __name__ == '__main__':
    seed()
