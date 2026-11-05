import csv
import io
import json
import time
from collections import Counter, defaultdict
from datetime import datetime

from flask import Blueprint, render_template, jsonify, request, g, Response, send_file
from flask_babel import gettext as _, format_date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from models import _now, db, Artiste, Oeuvre, libelle
from security import rate_limit, csv_safe

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
    """DataFrame des œuvres publiées, filtré en SQL, avec libellés traduits."""
    q = Oeuvre.publiees()
    if genre:
        q = q.filter(Oeuvre.genre_musical == genre)
    if langue:
        q = q.filter(Oeuvre.langue == langue)
    if region:
        q = q.filter(Artiste.region_origine == region)
    if decennie and str(decennie).isdigit():
        d = int(decennie)
        q = q.filter(Oeuvre.annee_sortie >= d, Oeuvre.annee_sortie < d + 10)

    rows = []
    for o in q.all():
        rows.append({
            'id':          o.id,
            'titre':       o.titre,
            'artiste':     o.artiste.nom,
            'type_oeuvre': libelle('type_oeuvre', o.type_oeuvre),
            'genre':       libelle('genre', o.genre_musical),
            'langue':      libelle('langue', o.langue),
            'annee':       o.annee_sortie,
            'decennie':    (o.annee_sortie // 10) * 10 if o.annee_sortie else None,
            'popularite_code': o.popularite or '',
            'popularite':  libelle('popularite', o.popularite) if o.popularite else _('Non renseignée'),
            'region':      libelle('region', o.artiste.region_origine),
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
        hovertemplate='<b>%{label}</b><br>%{value} ' + _('œuvre(s)') + ' — %{percent}<extra></extra>'
    )
    fig.update_layout(**base_layout(_('Répartition par genre musical'), h=340))
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
        hovertemplate='<b>%{x}</b> — %{y} ' + _('sortie(s)') + '<extra></extra>',
        name=_('Sorties')
    ))
    fig.update_layout(**base_layout(_('Évolution des sorties par année'), h=280))
    return fig_json(fig)


def chart_decennies(df):
    dec_counts = df.groupby('decennie').size().reset_index(name='Nombre')
    dec_counts = dec_counts.sort_values('decennie')
    dec_counts['Décennie'] = dec_counts['decennie'].apply(lambda x: f"{int(x)}s")
    fig = px.bar(dec_counts, x='Décennie', y='Nombre',
                 labels={'Décennie': _('Décennie'), 'Nombre': _('Nombre')},
                 color='Nombre',
                 color_continuous_scale=['#007A5E','#FCD116','#CE1126'],
                 text='Nombre')
    fig.update_traces(textposition='outside', textfont_color='#4a4035')
    fig.update_coloraxes(showscale=False)
    fig.update_layout(**base_layout(_('Productions par décennie'), h=300,
                                    extra=dict(xaxis=dict(**AXIS_STYLE, tickangle=-20))))
    return fig_json(fig)


def chart_langues(df):
    counts = df['langue'].value_counts().reset_index()
    counts.columns = ['Langue', 'Nombre']
    counts = counts.sort_values('Nombre')
    fig = px.bar(counts, x='Nombre', y='Langue', orientation='h',
                 labels={'Langue': _('Langue'), 'Nombre': _('Nombre')},
                 color='Nombre',
                 color_continuous_scale=['#007A5E','#FCD116','#CE1126'])
    fig.update_coloraxes(showscale=False)
    fig.update_traces(hovertemplate='<b>%{y}</b> — %{x} ' + _('œuvre(s)') + '<extra></extra>')
    fig.update_layout(**base_layout(_('Langues utilisées'), h=340))
    return fig_json(fig)


def chart_regions(df):
    counts = df['region'].value_counts().reset_index()
    counts.columns = ['Région', 'Nombre']
    fig = px.bar(counts, x='Région', y='Nombre',
                 labels={'Région': _('Région'), 'Nombre': _('Nombre')},
                 color='Nombre',
                 color_continuous_scale=['#007A5E','#FCD116','#CE1126'],
                 text='Nombre')
    fig.update_traces(textposition='outside', textfont_color='#4a4035')
    fig.update_coloraxes(showscale=False)
    fig.update_layout(**base_layout(_('Productions par région'), h=300,
                                    extra=dict(xaxis=dict(**AXIS_STYLE, tickangle=-30))))
    return fig_json(fig)


def chart_popularite(df):
    order = ['Locale', 'Nationale', 'Continentale', 'Internationale', '']
    colors_map = {'Locale': '#2d8a5e', 'Nationale': '#007A5E', 'Continentale': '#FCD116',
                  'Internationale': '#CE1126', '': '#3a3f45'}
    counts = df['popularite_code'].value_counts().reindex(order, fill_value=0)
    labels = [libelle('popularite', c) if c else _('Non renseignée') for c in counts.index]
    fig = go.Figure(go.Bar(
        x=labels, y=list(counts.values),
        marker_color=[colors_map[c] for c in counts.index],
        text=list(counts.values), textposition='outside',
        textfont=dict(color='#4a4035'),
        hovertemplate='<b>%{x}</b><br>%{y} ' + _('œuvre(s)') + '<extra></extra>'
    ))
    fig.update_layout(**base_layout(_('Rayonnement géographique'), h=280))
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
        hovertemplate='%{y} — %{x}<br><b>%{z} ' + _('œuvre(s)') + '</b><extra></extra>',
        showscale=True,
        colorbar=dict(
            tickfont=dict(color='#4a4035', size=10),
            outlinewidth=0, thickness=12
        )
    ))
    layout = base_layout(_('Genres × Décennies (heatmap)'), h=340,
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
    fig.update_layout(**base_layout(_("Types d'œuvres"), h=280))
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
            df['popularite_code'].isin(['Internationale','Continentale']).sum() / len(df) * 100, 1),
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

    # Valeurs disponibles pour les sélecteurs de filtres (requêtes DISTINCT)
    pub = Oeuvre.publiees()
    all_genres    = sorted(v for (v,) in pub.with_entities(Oeuvre.genre_musical).distinct())
    all_langues   = sorted(v for (v,) in pub.with_entities(Oeuvre.langue).distinct())
    all_regions   = sorted(v for (v,) in pub.with_entities(Artiste.region_origine).distinct())
    all_decennies = sorted({(a // 10) * 10 for (a,) in pub.with_entities(Oeuvre.annee_sortie).distinct() if a})

    total_oeuvres  = pub.count()
    total_artistes = Artiste.query.filter_by(statut='approuve').count()

    oeuvres_table = pub.order_by(Oeuvre.annee_sortie.desc()).limit(50).all()

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
    stats['graphiques_generes'] = list(build_all_graphs(df).keys())
    return jsonify(stats)




# ════════════════════════════════════════════════
#  CARTE + CHRONOLOGIE + EXPORTS
# ════════════════════════════════════════════════

REGIONS_CARTE = ['Adamaoua', 'Centre', 'Est', 'Extrême-Nord', 'Littoral',
                 'Nord', 'Nord-Ouest', 'Ouest', 'Sud', 'Sud-Ouest']


@dashboard_bp.route('/carte')
def carte():
    artistes_par_region = dict(
        db.session.query(Artiste.region_origine, db.func.count(Artiste.id))
        .filter_by(statut='approuve').group_by(Artiste.region_origine).all()
    )
    oeuvres_par_region = {}
    genres_par_region  = defaultdict(Counter)
    artistes_detail    = defaultdict(list)
    for a in Artiste.query.filter_by(statut='approuve').order_by(Artiste.nb_vues.desc()).all():
        r = a.region_origine
        oeuvres_region = a.oeuvres_approuvees
        oeuvres_par_region[r] = oeuvres_par_region.get(r, 0) + len(oeuvres_region)
        for o in oeuvres_region:
            genres_par_region[r][o.genre_musical] += 1
        artistes_detail[r].append({
            'id': a.id, 'nom': a.nom, 'type': libelle('type_artiste', a.type_artiste),
            'nb': len(oeuvres_region), 'photo': a.photo_url or '',
        })

    top_genre_region = {r: libelle('genre', g.most_common(1)[0][0])
                        for r, g in genres_par_region.items() if g}
    regions_libelles = {r: libelle('region', r) for r in REGIONS_CARTE + ['Diaspora']}

    return render_template('dashboard/carte.html',
        artistes_par_region=artistes_par_region,
        oeuvres_par_region=oeuvres_par_region,
        top_genre_region=top_genre_region,
        artistes_detail=dict(artistes_detail),
        toutes_regions=REGIONS_CARTE,
        regions_libelles=regions_libelles,
        total_artistes=Artiste.query.filter_by(statut='approuve').count(),
        total_oeuvres=Oeuvre.publiees().count())


@dashboard_bp.route('/chronologie')
def chronologie():
    oeuvres = Oeuvre.publiees().order_by(Oeuvre.annee_sortie).all()
    if not oeuvres:
        return render_template('dashboard/chronologie.html', decennies={}, oeuvres=[],
                               chart_json={}, total_oeuvres=0, nb_videos=0,
                               annee_min=1960, annee_max=_now().year)

    decennies = {}
    for o in oeuvres:
        dec = (o.annee_sortie // 10) * 10
        d = decennies.setdefault(dec, {'oeuvres': [], 'genres': Counter(), 'artistes': []})
        d['oeuvres'].append(o)
        d['genres'][o.genre_musical] += 1
        if o.artiste.nom not in d['artistes']:
            d['artistes'].append(o.artiste.nom)
    for d in decennies.values():
        d['top_genre'] = d['genres'].most_common(1)[0][0] if d['genres'] else None
        d['nb_oeuvres'] = len(d['oeuvres'])

    par_annee_genre = defaultdict(Counter)
    for o in oeuvres:
        par_annee_genre[o.annee_sortie][o.genre_musical] += 1
    annees_sorted = sorted(par_annee_genre)
    genres_all = sorted({o.genre_musical for o in oeuvres})
    couleurs = {'Makossa': '#007A5E', 'Bikutsi': '#FCD116', 'Afrobeat': '#CE1126', 'Jazz': '#4ecdc4',
                'R&B': '#ff6b35', 'Gospel': '#a855f7', 'Hip-hop': '#f59e0b'}

    fig = go.Figure()
    for i, genre in enumerate(genres_all):
        y_vals = [par_annee_genre[a].get(genre, 0) for a in annees_sorted]
        if not any(y_vals):
            continue
        nom = libelle('genre', genre)
        fig.add_trace(go.Bar(
            name=nom, x=annees_sorted, y=y_vals,
            marker_color=couleurs.get(genre, PALETTE[i % len(PALETTE)]),
            hovertemplate=f'<b>{nom}</b><br>%{{x}}: %{{y}} ' + _('sortie(s)') + '<extra></extra>'
        ))
    fig.update_layout(
        barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='DM Sans,sans-serif', color='#4a453e', size=12),
        margin=dict(t=20, b=50, l=40, r=20), height=320,
        xaxis=dict(color='#4a453e', gridcolor='rgba(0,0,0,0.05)', tickangle=-30),
        yaxis=dict(color='#4a453e', gridcolor='rgba(0,0,0,0.05)'),
        legend=dict(font=dict(color='#4a453e', size=10), bgcolor='rgba(0,0,0,0)',
                    orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        bargap=0.15,
    )

    return render_template('dashboard/chronologie.html',
        decennies=dict(sorted(decennies.items())),
        oeuvres=oeuvres,
        nb_videos=sum(1 for o in oeuvres if o.youtube_id),
        chart_json=json.loads(fig.to_json()),
        total_oeuvres=len(oeuvres),
        annee_min=oeuvres[0].annee_sortie,
        annee_max=oeuvres[-1].annee_sortie)


@dashboard_bp.route('/export/donnees.csv')
@rate_limit(20, 600, scope='export', methods=('GET',))
def export_csv():
    """Export public : données publiées uniquement, sans aucune donnée personnelle."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([_('ID'), _('Titre'), _('Artiste'), _('Région'), _('Type'), _('Genre'), _('Langue'),
                     _('Année'), _('Décennie'), _('Popularité'), _('Distinction'), _('Lien YouTube')])
    for o in Oeuvre.publiees().order_by(Oeuvre.annee_sortie).all():
        writer.writerow([csv_safe(v) for v in (
            o.id, o.titre, o.artiste.nom, libelle('region', o.artiste.region_origine),
            libelle('type_oeuvre', o.type_oeuvre), libelle('genre', o.genre_musical),
            libelle('langue', o.langue), o.annee_sortie, o.decennie or '',
            libelle('popularite', o.popularite) if o.popularite else '',
            o.distinction or '', o.youtube_url or '')])
    return Response('﻿' + output.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename=jackbeat_donnees.csv'})


_pdf_cache = {}
PDF_CACHE_SECONDS = 300


@dashboard_bp.route('/export/rapport.pdf')
@rate_limit(10, 600, scope='export-pdf', methods=('GET',))
def export_pdf():
    lang = g.get('lang', 'fr')
    cached = _pdf_cache.get(lang)
    if cached and time.time() - cached[0] < PDF_CACHE_SECONDS:
        data = cached[1]
    else:
        data = _build_pdf()
        _pdf_cache[lang] = (time.time(), data)
    return send_file(io.BytesIO(data), mimetype='application/pdf', as_attachment=True,
                     download_name=f'jackbeat_rapport_{datetime.now().strftime("%Y%m%d")}.pdf')


def _build_pdf():
    from xml.sax.saxutils import escape
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_CENTER

    artistes = Artiste.query.filter_by(statut='approuve').all()
    oeuvres  = Oeuvre.publiees().all()
    nb_a, nb_o = len(artistes), len(oeuvres)

    genres_count  = Counter(o.genre_musical for o in oeuvres)
    langues_count = Counter(o.langue for o in oeuvres)
    regions_count = Counter(a.region_origine for a in artistes)
    dec_count     = Counter((o.annee_sortie // 10) * 10 for o in oeuvres)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title='Jackbeat',
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2*cm)

    GREEN = colors.HexColor('#007A5E')
    RED   = colors.HexColor('#CE1126')
    GOLD  = colors.HexColor('#E6B800')
    DARK  = colors.HexColor('#1a1814')
    GRAY  = colors.HexColor('#8a8278')
    LGRAY = colors.HexColor('#f5f4f1')
    WHITE = colors.white

    def S(name, **kw): return ParagraphStyle(name, **kw)

    sT  = S('T',  fontSize=24, textColor=DARK, fontName='Helvetica-Bold', leading=30, spaceAfter=4)
    sST = S('ST', fontSize=12, textColor=GREEN, fontName='Helvetica-Bold', leading=16, spaceAfter=4)
    sSB = S('SB', fontSize=10, textColor=GRAY, fontName='Helvetica', leading=14, spaceAfter=18)
    sH2 = S('H2', fontSize=13, textColor=GREEN, fontName='Helvetica-Bold', leading=18, spaceBefore=16, spaceAfter=8)
    sB  = S('B',  fontSize=9,  textColor=DARK, fontName='Helvetica', leading=13, spaceAfter=6)
    sC  = S('C',  fontSize=8.5, textColor=DARK, fontName='Helvetica', leading=11)
    sFt = S('Ft', fontSize=7.5, textColor=GRAY, fontName='Helvetica', leading=11, alignment=TA_CENTER)

    def P(text):
        # Tout texte venant de la base est échappé : le moteur de Paragraph interprète le balisage
        return Paragraph(escape(str(text)), sC)

    def tbl(data, widths, hbg=GREEN):
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), hbg),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LGRAY]),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('TEXTCOLOR', (0, 1), (-1, -1), DARK),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#e0ddd7')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 7),
            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ]))
        return t

    W = doc.width
    story = []
    barre = Table([['', '', '']], colWidths=[W/3, W/3, W/3], rowHeights=[5])
    barre.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), GREEN),
        ('BACKGROUND', (1, 0), (1, 0), RED),
        ('BACKGROUND', (2, 0), (2, 0), GOLD),
    ]))
    maintenant = datetime.now()
    story += [barre, Spacer(1, .4*cm)]
    story.append(Paragraph('Jackbeat', sT))
    story.append(Paragraph(escape(_('Patrimoine Musical Camerounais')), sST))
    story.append(Paragraph(escape(_("Rapport d'analyse")) + f' · {format_date(maintenant, "long")}', sSB))
    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor('#e0ddd7'), spaceAfter=16))

    story.append(Paragraph(escape(_("Résumé de l'archive")), sH2))
    rayonnement = round(sum(1 for o in oeuvres if o.popularite in ('Internationale', 'Continentale'))
                        / max(nb_o, 1) * 100, 1)
    story.append(tbl([
        [_('Indicateur'), _('Valeur'), _('Détail')],
        [_('Artistes archivés'), str(nb_a), _('Approuvés et publiés')],
        [_('Œuvres archivées'),  str(nb_o), _('Chansons, albums, EP, lives')],
        [_('Genres musicaux'),   str(len(genres_count)), _('Styles représentés')],
        [_('Langues utilisées'), str(len(langues_count)), _('Langues de composition')],
        [_('Régions couvertes'), str(len(regions_count)), _('Sur 10 régions du Cameroun')],
        [_('Rayonnement continental ou plus'), f'{rayonnement}%', _('Part internationale')],
    ], [W*.42, W*.18, W*.4]))

    if oeuvres:
        ann = [o.annee_sortie for o in oeuvres]
        story.append(Spacer(1, .2*cm))
        story.append(Paragraph(escape(_('Période couverte : %(a)s – %(b)s (%(n)s ans)',
                                        a=min(ann), b=max(ann), n=max(ann) - min(ann))), sB))

    story.append(Paragraph(escape(_('Genres musicaux')), sH2))
    story.append(tbl(
        [[_('Genre'), _('Œuvres'), '%', _('Rang')]] +
        [[P(libelle('genre', g)), str(c), f'{c/max(nb_o,1)*100:.1f}%', f'#{i}']
         for i, (g, c) in enumerate(genres_count.most_common(), 1)],
        [W*.4, W*.15, W*.2, W*.25]
    ))

    story.append(Paragraph(escape(_('Diversité linguistique')), sH2))
    story.append(tbl(
        [[_('Langue'), _('Œuvres'), '%']] +
        [[P(libelle('langue', l)), str(c), f'{c/max(nb_o,1)*100:.1f}%'] for l, c in langues_count.most_common()],
        [W*.45, W*.2, W*.35], hbg=colors.HexColor('#005540')
    ))

    story.append(Paragraph(escape(_('Production par région')), sH2))
    oeuvres_reg = Counter(o.artiste.region_origine for o in oeuvres)
    story.append(tbl(
        [[_('Région'), _('Artistes'), _('Œuvres')]] +
        [[P(libelle('region', r)), str(c), str(oeuvres_reg.get(r, 0))] for r, c in regions_count.most_common()],
        [W*.45, W*.25, W*.3], hbg=RED
    ))

    story.append(Paragraph(escape(_('Évolution par décennie')), sH2))
    artistes_par_dec = defaultdict(set)
    for o in oeuvres:
        artistes_par_dec[(o.annee_sortie // 10) * 10].add(o.artiste_id)
    story.append(tbl(
        [[_('Décennie'), _('Œuvres'), _('Artistes actifs')]] +
        [[f'{d}s', str(dc), str(len(artistes_par_dec[d]))] for d, dc in sorted(dec_count.items())],
        [W*.3, W*.3, W*.4], hbg=colors.HexColor('#c9a800')
    ))

    story.append(Paragraph(escape(_('Catalogue des artistes')), sH2))
    nb_oeuvres_artiste = Counter(o.artiste_id for o in oeuvres)
    abbr = {'Soliste_H': _('H'), 'Soliste_F': _('F'), 'Groupe': _('G')}

    def periode(a):
        if not a.annee_debut:
            return '?'
        return f'{a.annee_debut}–{a.annee_fin}' if a.annee_fin else f'{a.annee_debut}–{_("présent")}'

    story.append(tbl(
        [[_('Artiste'), _('Région'), _('Type'), _('Œuvres'), _('Période')]] +
        [[P(a.nom), P(libelle('region', a.region_origine)), abbr.get(a.type_artiste, '?'),
          str(nb_oeuvres_artiste.get(a.id, 0)), periode(a)]
         for a in sorted(artistes, key=lambda x: x.nom.lower())],
        [W*.28, W*.2, W*.1, W*.12, W*.3], hbg=DARK
    ))

    story += [Spacer(1, .8*cm),
              HRFlowable(width=W, thickness=.5, color=colors.HexColor('#e0ddd7')),
              Spacer(1, .2*cm),
              Paragraph(escape(_('Jackbeat — Patrimoine Musical Camerounais · Rapport du %(d)s · INF 232 EC2',
                                 d=format_date(maintenant, 'short'))), sFt)]

    doc.build(story)
    return buf.getvalue()
