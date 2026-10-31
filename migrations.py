"""
migrations.py — Mise à jour douce et idempotente du schéma.

`db.create_all()` crée les tables manquantes mais n'ajoute jamais de colonne à
une table existante. Ce module compare chaque modèle au schéma réel et ajoute
les colonnes manquantes (SQLite comme PostgreSQL), chacune dans sa propre
transaction : un échec ne bloque pas les suivantes.
"""
import logging

from sqlalchemy import inspect, text

log = logging.getLogger('jackbeat.migrations')


def _default_sql(column, dialect):
    default = column.default
    if default is None or not getattr(default, 'is_scalar', False):
        return ''
    value = default.arg
    if isinstance(value, bool):
        if dialect.name == 'postgresql':
            return ' DEFAULT TRUE' if value else ' DEFAULT FALSE'
        return ' DEFAULT 1' if value else ' DEFAULT 0'
    if isinstance(value, (int, float)):
        return f' DEFAULT {value}'
    return ''


def upgrade_schema(db):
    engine = db.engine
    db.create_all()
    inspector = inspect(engine)
    added = []
    for table in db.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c['name'] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            col_type = column.type.compile(dialect=engine.dialect)
            default = _default_sql(column, engine.dialect)
            # NOT NULL impossible sans valeur par défaut sur une table existante
            not_null = ' NOT NULL' if (not column.nullable and default) else ''
            ddl = f'ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}{default}{not_null}'
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                added.append(f'{table.name}.{column.name}')
            except Exception as exc:  # colonne créée en parallèle par un autre worker, etc.
                log.warning('Migration ignorée (%s) : %s', ddl, exc)
    if added:
        log.info('Colonnes ajoutées : %s', ', '.join(added))
    return added
