from flask import Blueprint, render_template, jsonify, request
from models import db, Artiste, Oeuvre
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

dashboard_bp = Blueprint('dashboard_bp', __name__)

# ── Palette Jackbeat ────────────────────────────────────────
PALETTE = ['#007A5E','#FCD116','#CE1126','#00a87f','#c9a800',
           '#a30d1e','#2d8a5e','#e8b000','#ff6b35','#4ecdc4']

LAYOUT_BASE = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='DM Sans, sans-serif', color='#4a4035', size=12),
    margin=dict(t=36, b=50, l=50, r=20),
    legend=dict(font=dict(color='#4a4035'), bgcolor='rgba(0,0,0,0)'),
)

AXIS_STYLE = dict(
    color='#4a4035',
    gridcolor='rgba(0,0,0,0.05)',
    linecolor='rgba(0,0,0,0.1)',
    zerolinecolor='rgba(0,0,0,0.06)'
)


# ── Helpers ─────────────────────────────────────────────────

def build_df(genre=None, region=None, langue=None, decennie=None):
    """Construit un DataFrame filtré depuis les œuvres approuvées."""
    q = Oeuvre.query.filter_by(statut='approuve')
    if genre:
        q = q.filter(Oeuvre.genre_musical == genre)
    if langue:
        q = q.filter(Oeuvre.langue == langue)
    oeuvres = q.all()

    rows = []
    for o in oeuvres:
        artiste_region = o.artiste.region_origine if o.artiste else 'Inconnue'
        if region and artiste_region != region:
            continue
        dec = (o.annee_sortie // 10) * 10 if o.annee_sortie else None
        if decennie and dec != int(decennie):
            continue
        rows.append({
            'id':          o.id,
            'titre':       o.titre,
            'artiste':     o.artiste.nom if o.artiste else 'Inconnu',
            'type_oeuvre': o.type_oeuvre,
            'genre':       o.genre_musical,
            'langue':      o.langue,
            'annee':       o.annee_sortie,
            'decennie':    dec,
            'popularite':  o.popularite or 'Non renseignée',
            'region':      artiste_region,
            'distinction': bool(o.distinction),
        })
    return pd.DataFrame(rows)


def fig_json(fig):
    return json.loads(fig.to_json())


def base_layout(title, h=320, extra=None):
    l = dict(**LAYOUT_BASE,
             title=dict(text=title, font=dict(size=13, color='#e8e2d4'), x=0),
             height=h,
             xaxis=dict(**AXIS_STYLE),
             yaxis=dict(**AXIS_STYLE))
    if extra:
        l.update(extra)
    return l


# ── Graphiques ───────────────────────────────────────────────

def chart_genres(df):
    counts = df['genre'].value_counts().reset_index()
    counts.columns = ['Genre', 'Nombre']
    fig = px.pie(counts, names='Genre', values='Nombre',
                 color_discrete_sequence=PALETTE, hole=0.4)
    fig.update_traces(
        textinfo='label+percent', textfont_size=10,
        marker=dict(line=dict(color='rgba(0,0,0,0.35)', width=1.5)),
        hovertemplate='<b>%{label}</b><br>%{value} œuvre(s) — %{percent}<extra></extra>'
    )
    fig.update_layout(**base_layout('Répartition par genre musical', h=340))
    return fig_json(fig)


def chart_timeline(df):
    yearly = df.groupby('annee').size().reset_index(name='Sorties')
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=yearly['annee'], y=yearly['Sorties'],
        mode='lines+markers',
        line=dict(color='#FCD116', width=2.5, shape='spline'),
        marker=dict(size=7, color='#FCD116',
                    line=dict(color='#0a0d0f', width=1.5)),
        fill='tozeroy',
        fillcolor='rgba(252,209,22,0.07)',
        hovertemplate='<b>%{x}</b> — %{y} sortie(s)<extra></extra>',
        name='Sorties'
    ))
    fig.update_layout(**base_layout('Évolution des sorties par année', h=280))
    return fig_json(fig)


def chart_decennies(df):
    dec_counts = df.groupby('decennie').size().reset_index(name='Nombre')
    dec_counts = dec_counts.sort_values('decennie')
    dec_counts['Décennie'] = dec_counts['decennie'].apply(lambda x: f"{int(x)}s")
    fig = px.bar(dec_counts, x='Décennie', y='Nombre',
                 color='Nombre',
                 color_continuous_scale=['#007A5E','#FCD116','#CE1126'],
                 text='Nombre')
    fig.update_traces(textposition='outside', textfont_color='#4a4035')
    fig.update_coloraxes(showscale=False)
    fig.update_layout(**base_layout('Productions par décennie', h=300,
                                    extra=dict(xaxis=dict(**AXIS_STYLE, tickangle=-20))))
    return fig_json(fig)


def chart_langues(df):
    counts = df['langue'].value_counts().reset_index()
    counts.columns = ['Langue', 'Nombre']
    counts = counts.sort_values('Nombre')
    fig = px.bar(counts, x='Nombre', y='Langue', orientation='h',
                 color='Nombre',
                 color_continuous_scale=['#007A5E','#FCD116','#CE1126'])
    fig.update_coloraxes(showscale=False)
    fig.update_traces(hovertemplate='<b>%{y}</b> — %{x} œuvre(s)<extra></extra>')
    fig.update_layout(**base_layout('Langues utilisées', h=340))
    return fig_json(fig)


def chart_regions(df):
    counts = df['region'].value_counts().reset_index()
    counts.columns = ['Région', 'Nombre']
    fig = px.bar(counts, x='Région', y='Nombre',
                 color='Nombre',
                 color_continuous_scale=['#007A5E','#FCD116','#CE1126'],
                 text='Nombre')
    fig.update_traces(textposition='outside', textfont_color='#4a4035')
    fig.update_coloraxes(showscale=False)
    fig.update_layout(**base_layout('Productions par région', h=300,
                                    extra=dict(xaxis=dict(**AXIS_STYLE, tickangle=-30))))
    return fig_json(fig)


def chart_popularite(df):
    order = ['Locale','Nationale','Continentale','Internationale','Non renseignée']
    counts = df['popularite'].value_counts().reindex(order, fill_value=0).reset_index()
    counts.columns = ['Popularité', 'Nombre']
    colors_map = {
        'Locale':          '#2d8a5e',
        'Nationale':       '#007A5E',
        'Continentale':    '#FCD116',
        'Internationale':  '#CE1126',
        'Non renseignée':  '#3a3f45'
    }
    fig = go.Figure(go.Bar(
        x=counts['Popularité'], y=counts['Nombre'],
        marker_color=[colors_map.get(p, '#555') for p in counts['Popularité']],
        text=counts['Nombre'], textposition='outside',
        textfont=dict(color='#4a4035'),
        hovertemplate='<b>%{x}</b><br>%{y} œuvre(s)<extra></extra>'
    ))
    fig.update_layout(**base_layout('Rayonnement géographique', h=280))
    return fig_json(fig)


def chart_heatmap(df):
    """Heatmap genre × décennie."""
    if df.empty or df['decennie'].isna().all():
        return None
    pivot = df.groupby(['decennie','genre']).size().unstack(fill_value=0)
    if pivot.empty:
        return None
    pivot.index = [f"{int(d)}s" for d in pivot.index]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=list(pivot.columns),
        y=list(pivot.index),
        colorscale=[[0,'#f0faf6'],[0.25,'#a8dcc8'],[0.55,'#007A5E'],[0.8,'#005540'],[1.0,'#003829']],
        hovertemplate='%{y} — %{x}<br><b>%{z} œuvre(s)</b><extra></extra>',
        showscale=True,
        colorbar=dict(
            tickfont=dict(color='#4a4035', size=10),
            outlinewidth=0, thickness=12
        )
    ))
    layout = base_layout('Genres × Décennies (heatmap)', h=340,
                          extra=dict(
                              xaxis=dict(**AXIS_STYLE, tickangle=-30),
                              yaxis=dict(**AXIS_STYLE)
                          ))
    # Fond blanc explicite pour la heatmap
    layout['paper_bgcolor'] = '#ffffff'
    layout['plot_bgcolor']  = '#ffffff'
    fig.update_layout(**layout)
    return fig_json(fig)


def chart_types(df):
    counts = df['type_oeuvre'].value_counts().reset_index()
    counts.columns = ['Type', 'Nombre']
    fig = px.pie(counts, names='Type', values='Nombre',
                 color_discrete_sequence=PALETTE, hole=0.4)
    fig.update_traces(
        textinfo='label+value',
        marker=dict(line=dict(color='rgba(0,0,0,0.35)', width=1.5))
    )
    fig.update_layout(**base_layout("Types d'œuvres", h=280))
    return fig_json(fig)


def build_all_graphs(df):
    if df.empty:
        return {}
    g = {}
    g['genres']     = chart_genres(df)
    g['timeline']   = chart_timeline(df)
    g['decennies']  = chart_decennies(df) if not df['decennie'].isna().all() else None
    g['langues']    = chart_langues(df)
    g['regions']    = chart_regions(df)
    g['popularite'] = chart_popularite(df)
    g['heatmap']    = chart_heatmap(df)
    g['types']      = chart_types(df)
    return {k: v for k, v in g.items() if v is not None}


def compute_stats(df):
    if df.empty:
        return {}
    return {
        'total_oeuvres':     int(len(df)),
        'total_artistes':    int(df['artiste'].nunique()),
        'annee_min':         int(df['annee'].min()),
        'annee_max':         int(df['annee'].max()),
        'genre_top':         df['genre'].value_counts().index[0],
        'genre_top_pct':     round(df['genre'].value_counts().iloc[0] / len(df) * 100, 1),
        'langue_top':        df['langue'].value_counts().index[0],
        'region_top':        df['region'].value_counts().index[0],
        'decennie_top':      f"{int(df['decennie'].value_counts().index[0])}s"
                             if not df['decennie'].isna().all() else '—',
        'avec_distinction':  int(df['distinction'].sum()),
        'pct_rayonnement':   round(
            df['popularite'].isin(['Internationale','Continentale']).sum() / len(df) * 100, 1),
        'genres_count':      int(df['genre'].nunique()),
        'langues_count':     int(df['langue'].nunique()),
        'regions_count':     int(df['region'].nunique()),
    }


# ── Routes ──────────────────────────────────────────────────

@dashboard_bp.route('/')
def index():
    genre    = request.args.get('genre', '')
    region   = request.args.get('region', '')
    langue   = request.args.get('langue', '')
    decennie = request.args.get('decennie', '')

    df = build_df(
        genre=genre or None, region=region or None,
        langue=langue or None, decennie=decennie or None
    )

    graphs = build_all_graphs(df)
    stats  = compute_stats(df)

    # Valeurs disponibles pour les sélecteurs de filtres
    all_genres    = sorted(set(
        o.genre_musical for o in Oeuvre.query.filter_by(statut='approuve').all()))
    all_langues   = sorted(set(
        o.langue for o in Oeuvre.query.filter_by(statut='approuve').all()))
    all_regions   = sorted(set(
        a.region_origine for a in Artiste.query.filter_by(statut='approuve').all()))
    all_decennies = sorted(set(
        (o.annee_sortie // 10) * 10
        for o in Oeuvre.query.filter_by(statut='approuve').all()
        if o.annee_sortie))

    total_oeuvres  = Oeuvre.query.filter_by(statut='approuve').count()
    total_artistes = Artiste.query.filter_by(statut='approuve').count()

    oeuvres_table = (Oeuvre.query.filter_by(statut='approuve')
                     .order_by(Oeuvre.annee_sortie.desc()).limit(50).all())

    actifs = dict(genre=genre, region=region, langue=langue, decennie=decennie)

    return render_template(
        'dashboard/index.html',
        graphs=graphs,
        stats=stats,
        total_oeuvres=total_oeuvres,
        total_artistes=total_artistes,
        all_genres=all_genres,
        all_langues=all_langues,
        all_regions=all_regions,
        all_decennies=all_decennies,
        oeuvres_table=oeuvres_table,
        actifs=actifs,
        filtres_actifs=any(actifs.values()),
    )


@dashboard_bp.route('/api/stats')
def api_stats():
    """Endpoint JSON — utile pour tests en terminal."""
    df    = build_df()
    stats = compute_stats(df)
    stats['graphiques_generés'] = list(build_all_graphs(df).keys())
    return jsonify(stats)
