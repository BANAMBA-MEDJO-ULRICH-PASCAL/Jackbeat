"""
seed_data.py — Peuple la base de données avec des données de test.
Exécuter : python seed_data.py
"""
from app import create_app
from models import db, Artiste, Oeuvre

app = create_app('development')

SAMPLE_DATA = [
    {
        'artiste': {'nom': 'Manu Dibango', 'region_origine': 'Littoral', 'type_artiste': 'Soliste_H',
                    'annee_debut': 1960, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Soul Makossa', 'type_oeuvre': 'Chanson', 'genre_musical': 'Makossa',
             'langue': 'Duala', 'annee_sortie': 1972, 'popularite': 'Internationale',
             'distinction': 'Billboard Hot 100 — 1973'},
        ]
    },
    {
        'artiste': {'nom': 'Charlotte Dipanda', 'region_origine': 'Littoral', 'type_artiste': 'Soliste_F',
                    'annee_debut': 2005, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Ndo Kolo', 'type_oeuvre': 'Chanson', 'genre_musical': 'Makossa',
             'langue': 'Duala', 'annee_sortie': 2009, 'popularite': 'Nationale'},
            {'titre': 'De toutes les couleurs', 'type_oeuvre': 'Album', 'genre_musical': 'R&B',
             'langue': 'Français', 'annee_sortie': 2012, 'popularite': 'Continentale'},
        ]
    },
    {
        'artiste': {'nom': 'Anne-Marie Nzié', 'region_origine': 'Littoral', 'type_artiste': 'Soliste_F',
                    'annee_debut': 1955, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Ayo', 'type_oeuvre': 'Chanson', 'genre_musical': 'Makossa',
             'langue': 'Duala', 'annee_sortie': 1968, 'popularite': 'Nationale'},
        ]
    },
    {
        'artiste': {'nom': 'Maahlox le Vibeur', 'region_origine': 'Centre', 'type_artiste': 'Soliste_H',
                    'annee_debut': 2010, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Ma Lova', 'type_oeuvre': 'Chanson', 'genre_musical': 'Bikutsi',
             'langue': 'Ewondo', 'annee_sortie': 2012, 'popularite': 'Nationale'},
        ]
    },
    {
        'artiste': {'nom': 'Koppo', 'region_origine': 'Centre', 'type_artiste': 'Soliste_H',
                    'annee_debut': 2005, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Kotto Bass', 'type_oeuvre': 'Chanson', 'genre_musical': 'Bikutsi',
             'langue': 'Ewondo', 'annee_sortie': 2008, 'popularite': 'Nationale'},
        ]
    },
    {
        'artiste': {'nom': 'Locko', 'region_origine': 'Littoral', 'type_artiste': 'Soliste_H',
                    'annee_debut': 2015, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Je t\'aime un peu', 'type_oeuvre': 'Chanson', 'genre_musical': 'Afrobeat',
             'langue': 'Français', 'annee_sortie': 2017, 'popularite': 'Continentale'},
            {'titre': 'Doux', 'type_oeuvre': 'Chanson', 'genre_musical': 'Afrobeat',
             'langue': 'Français', 'annee_sortie': 2020, 'popularite': 'Continentale'},
        ]
    },
    {
        'artiste': {'nom': 'Les Têtes Brulées', 'region_origine': 'Centre', 'type_artiste': 'Groupe',
                    'annee_debut': 1987, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Hot Koki', 'type_oeuvre': 'Album', 'genre_musical': 'Bikutsi',
             'langue': 'Français', 'annee_sortie': 1988, 'popularite': 'Internationale',
             'distinction': 'Documentaire BBC — 1992'},
        ]
    },
    {
        'artiste': {'nom': 'Richard Bona', 'region_origine': 'Sud', 'type_artiste': 'Soliste_H',
                    'annee_debut': 1990, 'statut': 'approuve'},
        'oeuvres': [
            {'titre': 'Munia: The Tale', 'type_oeuvre': 'Album', 'genre_musical': 'Jazz',
             'langue': 'Multilingue', 'annee_sortie': 1999, 'popularite': 'Internationale'},
        ]
    },
]


def seed():
    with app.app_context():
        if Artiste.query.count() > 0:
            print("⚠️  La base de données contient déjà des données. Seed ignoré.")
            return

        for entry in SAMPLE_DATA:
            a = entry['artiste']
            artiste = Artiste(**a)
            db.session.add(artiste)
            db.session.flush()

            for o in entry['oeuvres']:
                oeuvre = Oeuvre(artiste_id=artiste.id, statut='approuve', **o)
                db.session.add(oeuvre)

        db.session.commit()
        print(f"✅ {Artiste.query.count()} artistes et {Oeuvre.query.count()} œuvres ajoutés !")


if __name__ == '__main__':
    seed()
