"""
seed_data.py — Données de démonstration VÉRIFIÉES.
"""
from app import create_app
from models import db, Artiste, Oeuvre

app = create_app('development')

SAMPLE_DATA = [
    {
        'artiste': {
            'nom':'Manu Dibango', 'region_origine':'Littoral', 'type_artiste':'Soliste_H',
            'annee_debut':1960, 'annee_fin':2020, 'statut':'approuve',
            'biographie':'Légende mondiale du Makossa, saxophoniste et pianiste. Son titre Soul Makossa (1972) a influencé Michael Jackson et Rihanna.',
        },
        'oeuvres': [
            {'titre':'Soul Makossa','type_oeuvre':'Chanson','genre_musical':'Makossa',
             'langue':'Duala','annee_sortie':1972,'popularite':'Internationale',
             'distinction':'Chanson africaine la plus samplée de l\'histoire',
             'lien_youtube':'https://www.youtube.com/watch?v=PblSmVR7hCk',
             'description':'Titre emblématique du Makossa, samplé par de nombreux artistes internationaux dont Michael Jackson et Rihanna.'},
        ]
    },
    {
        'artiste': {
            'nom':'Charlotte Dipanda', 'region_origine':'Centre', 'type_artiste':'Soliste_F',
            'annee_debut':2002, 'statut':'approuve',
            'biographie':'Née à Yaoundé en 1985, voix incontournable de la musique acoustique camerounaise contemporaine.',
        },
        'oeuvres': [
            {'titre':'Ndolo Bukatè','type_oeuvre':'Chanson','genre_musical':'Afrobeat',
             'langue':'Duala','annee_sortie':2015,'popularite':'Nationale',
             'lien_youtube':'https://www.youtube.com/watch?v=MPYGv033Rs8',
             'description':'Extrait de l\'album "Massa" (2015), chanté en langue Duala.'},
        ]
    },
    {
        'artiste': {
            'nom':'Anne-Marie Nzié', 'region_origine':'Littoral', 'type_artiste':'Soliste_F',
            'annee_debut':1955, 'annee_fin':2020, 'statut':'approuve',
            'biographie':'Pionnière de la musique camerounaise, surnommée "La grande dame de la chanson camerounaise".',
        },
        'oeuvres': []
    },
    {
        'artiste': {
            'nom':'Koppo', 'region_origine':'Centre', 'type_artiste':'Soliste_H',
            'annee_debut':2003, 'statut':'approuve',
            'biographie':'Figure du Bikutsi moderne et de la scène musicale camerounaise du Centre.',
        },
        'oeuvres': []
    },
    {
        'artiste': {
            'nom':'Locko', 'region_origine':'Littoral', 'type_artiste':'Soliste_H',
            'annee_debut':2015, 'statut':'approuve',
            'biographie':'Artiste afropop de la nouvelle génération camerounaise.',
        },
        'oeuvres': []
    },
    {
        'artiste': {
            'nom':'Les Têtes Brulées', 'region_origine':'Centre', 'type_artiste':'Groupe',
            'annee_debut':1985, 'annee_fin':1995, 'statut':'approuve',
            'biographie':'Groupe de Bikutsi révolutionnaire, connu pour leur look punk-africain. Leur guitariste Théodore "Zanzibar" Epeme imitait le son du balafon avec de la mousse sur les cordes.',
        },
        'oeuvres': [
            {'titre':'Hot Heads','type_oeuvre':'Album','genre_musical':'Bikutsi',
             'langue':'Multilingue','annee_sortie':1990,'popularite':'Internationale',
             'distinction':'Tournée nord-américaine en 1990',
             'description':'Album emblématique du Bikutsi moderne, enregistré en France.',
             'lien_youtube': None},
        ]
    },
    {
        'artiste': {
            'nom':'Richard Bona', 'region_origine':'Est', 'type_artiste':'Soliste_H',
            'annee_debut':1990, 'statut':'approuve',
            'biographie':'Bassiste virtuose de renommée mondiale, originaire de Minta (Est-Cameroun), ambassadeur du jazz afro-fusion.',
        },
        'oeuvres': [
            {'titre':'Munia (The Tale)','type_oeuvre':'Album','genre_musical':'Jazz',
             'langue':'Multilingue','annee_sortie':2003,'popularite':'Internationale',
             'description':'Troisième album studio de Richard Bona, sorti le 22 septembre 2003 chez Universal Music France.',
             'lien_youtube': None},
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
        nb_yt = Oeuvre.query.filter(Oeuvre.lien_youtube != None).count()
        print(f"✅ {Artiste.query.count()} artistes · {Oeuvre.query.count()} œuvres "
              f"({nb_yt} avec lien YouTube vérifié) ajoutés.")


if __name__ == '__main__':
    seed()
