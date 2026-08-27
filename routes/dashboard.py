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


# ════════════════════════════════════════════════
#  PHASE 3 — CARTE + CHRONOLOGIE + PDF
# ════════════════════════════════════════════════

@dashboard_bp.route('/carte')
def carte():
    from models import Artiste, Oeuvre
    from sqlalchemy import func
    artistes_par_region = dict(
        db.session.query(Artiste.region_origine, func.count(Artiste.id))
        .filter_by(statut='approuve').group_by(Artiste.region_origine).all()
    )
    oeuvres_par_region = {}
    genres_par_region  = {}
    artistes_detail    = {}
    for a in Artiste.query.filter_by(statut='approuve').order_by(Artiste.nb_vues.desc()).all():
        r = a.region_origine
        oeuvres_region = a.oeuvres_approuvees
        oeuvres_par_region[r] = oeuvres_par_region.get(r, 0) + len(oeuvres_region)
        for o in oeuvres_region:
            if r not in genres_par_region: genres_par_region[r] = {}
            genres_par_region[r][o.genre_musical] = genres_par_region[r].get(o.genre_musical, 0) + 1
        if r not in artistes_detail: artistes_detail[r] = []
        artistes_detail[r].append(a)

    top_genre_region = {r: max(g, key=g.get) for r, g in genres_par_region.items()}
    toutes_regions = ['Adamaoua','Centre','Est','Extrême-Nord','Littoral',
                      'Nord','Nord-Ouest','Ouest','Sud','Sud-Ouest']

    return render_template('dashboard/carte.html',
        artistes_par_region=artistes_par_region,
        oeuvres_par_region=oeuvres_par_region,
        top_genre_region=top_genre_region,
        artistes_detail=artistes_detail,
        toutes_regions=toutes_regions,
        total_artistes=Artiste.query.filter_by(statut='approuve').count(),
        total_oeuvres =Oeuvre.query.filter_by(statut='approuve').count())


@dashboard_bp.route('/chronologie')
def chronologie():
    from models import Artiste, Oeuvre
    from collections import defaultdict

    oeuvres = Oeuvre.query.filter_by(statut='approuve').order_by(Oeuvre.annee_sortie).all()
    if not oeuvres:
        return render_template('dashboard/chronologie.html', decennies={}, oeuvres=[],
                               chart_json={}, total_oeuvres=0, annee_min=1960, annee_max=2024)

    decennies = {}
    for o in oeuvres:
        dec = (o.annee_sortie // 10) * 10
        if dec not in decennies:
            decennies[dec] = {'oeuvres': [], 'genres': {}, 'artistes': set()}
        decennies[dec]['oeuvres'].append(o)
        decennies[dec]['genres'][o.genre_musical] = decennies[dec]['genres'].get(o.genre_musical, 0) + 1
        if o.artiste: decennies[dec]['artistes'].add(o.artiste.nom)

    for d in decennies.values():
        d['artistes']  = list(d['artistes'])
        d['top_genre'] = max(d['genres'], key=d['genres'].get) if d['genres'] else '—'
        d['nb_oeuvres']= len(d['oeuvres'])

    par_annee_genre = defaultdict(lambda: defaultdict(int))
    for o in oeuvres:
        par_annee_genre[o.annee_sortie][o.genre_musical] += 1

    annees_sorted = sorted(par_annee_genre.keys())
    genres_all    = sorted(set(o.genre_musical for o in oeuvres))
    PALETTE = {'Makossa':'#007A5E','Bikutsi':'#FCD116','Afrobeat':'#CE1126','Jazz':'#4ecdc4',
               'R&B':'#ff6b35','Gospel':'#a855f7','Hip-hop':'#f59e0b'}

    import plotly.graph_objects as go
    fig = go.Figure()
    for genre in genres_all:
        y_vals = [par_annee_genre[a].get(genre, 0) for a in annees_sorted]
        if not any(y_vals): continue
        fig.add_trace(go.Bar(
            name=genre, x=annees_sorted, y=y_vals,
            marker_color=PALETTE.get(genre, '#888'),
            hovertemplate=f'<b>{genre}</b><br>%{{x}}: %{{y}} sortie(s)<extra></extra>'
        ))
    fig.update_layout(
        barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='DM Sans,sans-serif', color='#4a453e', size=12),
        margin=dict(t=20,b=50,l=40,r=20), height=320,
        xaxis=dict(color='#4a453e', gridcolor='rgba(0,0,0,0.05)', tickangle=-30),
        yaxis=dict(color='#4a453e', gridcolor='rgba(0,0,0,0.05)'),
        legend=dict(font=dict(color='#4a453e',size=10),bgcolor='rgba(0,0,0,0)',
                    orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1),
        bargap=0.15,
    )

    return render_template('dashboard/chronologie.html',
        decennies=dict(sorted(decennies.items())),
        oeuvres=oeuvres,
        chart_json=json.loads(fig.to_json()),
        total_oeuvres=len(oeuvres),
        annee_min=oeuvres[0].annee_sortie,
        annee_max=oeuvres[-1].annee_sortie)


@dashboard_bp.route('/export/rapport.pdf')
def export_pdf():
    from models import Artiste, Oeuvre
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_CENTER
    from io import BytesIO
    from datetime import datetime
    from collections import Counter
    from flask import send_file

    artistes = Artiste.query.filter_by(statut='approuve').all()
    oeuvres  = Oeuvre.query.filter_by(statut='approuve').all()
    nb_a, nb_o = len(artistes), len(oeuvres)

    genres_count  = Counter(o.genre_musical for o in oeuvres)
    langues_count = Counter(o.langue for o in oeuvres)
    regions_count = Counter(a.region_origine for a in artistes)
    dec_count     = Counter((o.annee_sortie//10)*10 for o in oeuvres)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
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
    sFt = S('Ft', fontSize=7.5,textColor=GRAY, fontName='Helvetica', leading=11, alignment=TA_CENTER)

    def tbl(data, widths, hbg=GREEN):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),hbg),
            ('TEXTCOLOR',(0,0),(-1,0),WHITE),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),8.5),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,LGRAY]),
            ('FONTNAME',(0,1),(-1,-1),'Helvetica'),
            ('TEXTCOLOR',(0,1),(-1,-1),DARK),
            ('ALIGN',(1,0),(-1,-1),'CENTER'),
            ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#e0ddd7')),
            ('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),7),
            ('RIGHTPADDING',(0,0),(-1,-1),7),
        ]))
        return t

    W = doc.width
    story = []
    barre = Table([['','','']], colWidths=[W/3,W/3,W/3], rowHeights=[5])
    barre.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,0),GREEN),
        ('BACKGROUND',(1,0),(1,0),RED),
        ('BACKGROUND',(2,0),(2,0),GOLD),
    ]))
    story += [barre, Spacer(1,.4*cm)]
    story.append(Paragraph('Jackbeat', sT))
    story.append(Paragraph('Patrimoine Musical Camerounais', sST))
    story.append(Paragraph(f'Rapport d\'analyse · {datetime.now().strftime("%d/%m/%Y %H:%M")}', sSB))
    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor('#e0ddd7'), spaceAfter=16))

    story.append(Paragraph('Résumé de l\'archive', sH2))
    story.append(tbl([
        ['Indicateur','Valeur','Détail'],
        ['Artistes archivés', str(nb_a), 'Approuvés et publiés'],
        ['Œuvres archivées',  str(nb_o), 'Chansons, albums, EP, lives'],
        ['Genres musicaux',   str(len(genres_count)), 'Styles représentés'],
        ['Langues utilisées', str(len(langues_count)),'Langues de composition'],
        ['Régions couverte',  str(len(regions_count)),'Sur 10 régions du Cameroun'],
        ['Rayonnement ≥ continental',
         f'{round(sum(1 for o in oeuvres if o.popularite in ["Internationale","Continentale"])/max(nb_o,1)*100,1)}%',
         'Part internationale'],
    ], [W*.42,W*.18,W*.4]))

    if oeuvres:
        ann = [o.annee_sortie for o in oeuvres]
        story.append(Spacer(1,.2*cm))
        story.append(Paragraph(f'Période couverte : <b>{min(ann)} – {max(ann)}</b> ({max(ann)-min(ann)} ans)', sB))

    story.append(Paragraph('Genres musicaux', sH2))
    story.append(tbl(
        [['Genre','Œuvres','%','Rang']] +
        [[g, str(c), f'{c/max(nb_o,1)*100:.1f}%', f'#{i}'] for i,(g,c) in enumerate(genres_count.most_common(),1)],
        [W*.4,W*.15,W*.2,W*.25]
    ))

    story.append(Paragraph('Diversité linguistique', sH2))
    story.append(tbl(
        [['Langue','Œuvres','%']] +
        [[l, str(c), f'{c/max(nb_o,1)*100:.1f}%'] for l,c in langues_count.most_common()],
        [W*.45,W*.2,W*.35], hbg=colors.HexColor('#005540')
    ))

    story.append(Paragraph('Production par région', sH2))
    oeuvres_reg = {}
    for a in artistes:
        oeuvres_reg[a.region_origine] = oeuvres_reg.get(a.region_origine,0) + len(a.oeuvres_approuvees)
    story.append(tbl(
        [['Région','Artistes','Œuvres']] +
        [[r, str(c), str(oeuvres_reg.get(r,0))] for r,c in regions_count.most_common()],
        [W*.45,W*.25,W*.3], hbg=RED
    ))

    story.append(Paragraph('Évolution par décennie', sH2))
    story.append(tbl(
        [['Décennie','Œuvres','Artistes actifs']] +
        [[f'{d}s', str(dc), str(len(set(
            a.nom for a in artistes for o in a.oeuvres_approuvees if (o.annee_sortie//10)*10==d
        )))] for d,dc in sorted(dec_count.items())],
        [W*.3,W*.3,W*.4], hbg=colors.HexColor('#c9a800')
    ))

    story.append(Paragraph('Catalogue des artistes', sH2))
    story.append(tbl(
        [['Artiste','Région','Type','Œuvres','Période']] +
        [[a.nom, a.region_origine,
          a.type_artiste.replace('Soliste_H','H').replace('Soliste_F','F').replace('Groupe','G'),
          str(len(a.oeuvres_approuvees)),
          f'{a.annee_debut or "?"}{"–"+str(a.annee_fin) if a.annee_fin else ("–présent" if a.annee_debut else "")}']
         for a in sorted(artistes, key=lambda x: x.nom)],
        [W*.28,W*.2,W*.1,W*.12,W*.3], hbg=DARK
    ))

    story += [Spacer(1,.8*cm),
              HRFlowable(width=W,thickness=.5,color=colors.HexColor('#e0ddd7')),
              Spacer(1,.2*cm),
              Paragraph(f'Jackbeat — Patrimoine Musical Camerounais · Rapport du {datetime.now().strftime("%d/%m/%Y")} · INF 232 EC2', sFt)]

    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name=f'jackbeat_rapport_{datetime.now().strftime("%Y%m%d")}.pdf')
