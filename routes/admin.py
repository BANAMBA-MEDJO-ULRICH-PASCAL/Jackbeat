import csv
import io
import json
from datetime import datetime, timedelta

from flask import (Blueprint, render_template, redirect, url_for, flash, request,
                   Response, jsonify, session, current_app, abort)
from flask_babel import gettext as _
from flask_login import login_user, logout_user, login_required, current_user
from markupsafe import Markup, escape
from werkzeug.security import generate_password_hash, check_password_hash

from forms import (AdminArtisteForm, AdminOeuvreForm, LoginForm, TotpForm,
                   PasswordChangeForm, TotpSetupForm, TotpDisableForm)
from models import (_now, db, Admin, Artiste, Oeuvre, Like, Commentaire, Signalement,
                    LoginAttempt, AuditLog, libelle)
from security import (ip_hash, safe_redirect_target, totp_generate_secret, totp_verify,
                      totp_uri, totp_qr_svg, generate_backup_codes, consume_backup_code,
                      password_problems, csv_safe)

admin_bp = Blueprint('admin_bp', __name__)

# Hash factice : vérifié quand l'identifiant n'existe pas, pour que le temps
# de réponse ne révèle pas quels comptes existent.
_DUMMY_HASH = generate_password_hash('jackbeat-dummy-password', method='scrypt')

STATUTS_VALIDES = ('en_attente', 'approuve', 'rejete')


# ════════════════════════════════════════════════
#  OUTILS
# ════════════════════════════════════════════════

def audit(action, cible=None, details=None, cible_type=None):
    entry = AuditLog(
        admin_id=current_user.id if current_user.is_authenticated else None,
        admin_username=current_user.username if current_user.is_authenticated else None,
        action=action,
        cible_type=cible_type or (cible.__tablename__.rstrip('s') if cible is not None else None),
        cible_id=getattr(cible, 'id', None),
        cible_nom=(getattr(cible, 'nom', None) or getattr(cible, 'titre', None)
                   or getattr(cible, 'username', None)),
        details=json.dumps(details, ensure_ascii=False, default=str) if details else None,
        ip_hash=ip_hash(),
    )
    db.session.add(entry)


def diff(avant, apres):
    return {k: [avant.get(k), apres.get(k)] for k in apres if avant.get(k) != apres.get(k)}


def retour(default_endpoint, **kwargs):
    return redirect(safe_redirect_target(request.form.get('next'), request.referrer,
                                         default=url_for(default_endpoint, **kwargs)))


def lien(url, texte):
    return Markup('<a href="{}">{}</a>').format(url, texte)


# ════════════════════════════════════════════════
#  AUTHENTIFICATION (mot de passe + double facteur)
# ════════════════════════════════════════════════

def _fenetre():
    return _now() - timedelta(minutes=current_app.config['LOGIN_LOCKOUT_MINUTES'])


def _connexion_bloquee(username):
    depuis = _fenetre()
    echecs_ip = LoginAttempt.query.filter(LoginAttempt.ip_hash == ip_hash(),
                                          LoginAttempt.success.is_(False),
                                          LoginAttempt.created_at >= depuis).count()
    if echecs_ip >= current_app.config['LOGIN_MAX_FAILS_PER_IP']:
        return True
    if username:
        echecs_user = LoginAttempt.query.filter(LoginAttempt.username == username,
                                                LoginAttempt.success.is_(False),
                                                LoginAttempt.created_at >= depuis).count()
        if echecs_user >= current_app.config['LOGIN_MAX_FAILS_PER_USER']:
            return True
    return False


def _noter_tentative(username, success):
    db.session.add(LoginAttempt(username=(username or '')[:80], ip_hash=ip_hash(), success=success))
    db.session.commit()


def _ouvrir_session(admin, next_url):
    lang = session.get('lang')
    session.clear()                      # nouvelle session : empêche la fixation de session
    if lang:
        session['lang'] = lang
    session.permanent = True
    login_user(admin, remember=False)
    admin.last_login_at = _now()
    _noter_tentative(admin.username, True)
    # Purge des tentatives anciennes (> 30 jours)
    LoginAttempt.query.filter(LoginAttempt.created_at < _now() - timedelta(days=30)).delete()
    audit('connexion', admin, cible_type='admin')
    db.session.commit()
    flash(_("Connexion réussie. Bienvenue dans l'espace admin Jackbeat."), 'success')
    return redirect(safe_redirect_target(next_url, default=url_for('admin_bp.dashboard')))


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_bp.dashboard'))

    form = LoginForm()
    error = None
    if form.validate_on_submit():
        username = form.username.data
        if _connexion_bloquee(username):
            current_app.logger.warning('Connexion admin bloquée (trop d’échecs) pour %r', username)
            error = _('Trop de tentatives échouées. Réessayez dans %(n)d minutes.',
                      n=current_app.config['LOGIN_LOCKOUT_MINUTES'])
        else:
            admin = Admin.query.filter_by(username=username).first()
            ok = check_password_hash(admin.password_hash if admin else _DUMMY_HASH, form.password.data)
            if admin and ok:
                next_url = request.args.get('next')
                if admin.totp_enabled:
                    session['2fa'] = {'id': admin.id, 'v': admin.session_version,
                                      'ts': _now().timestamp(), 'next': next_url}
                    return redirect(url_for('admin_bp.login_verification'))
                return _ouvrir_session(admin, next_url)
            _noter_tentative(username, False)
            current_app.logger.warning('Échec de connexion admin pour %r', username)
            error = _('Identifiants incorrects. Veuillez réessayer.')

    return render_template('admin/login.html', form=form, error=error)


@admin_bp.route('/login/verification', methods=['GET', 'POST'])
def login_verification():
    pending = session.get('2fa')
    if not pending or _now().timestamp() - pending['ts'] > 300:
        session.pop('2fa', None)
        flash(_('Session de vérification expirée. Reconnectez-vous.'), 'warning')
        return redirect(url_for('admin_bp.login'))
    admin = db.session.get(Admin, pending['id'])
    if not admin or admin.session_version != pending['v'] or not admin.totp_enabled:
        session.pop('2fa', None)
        return redirect(url_for('admin_bp.login'))

    form = TotpForm()
    error = None
    if form.validate_on_submit():
        if _connexion_bloquee(admin.username):
            error = _('Trop de tentatives échouées. Réessayez dans %(n)d minutes.',
                      n=current_app.config['LOGIN_LOCKOUT_MINUTES'])
        else:
            code = form.code.data
            step = totp_verify(admin.totp_secret, code, admin.totp_last_step)
            if step is not None:
                admin.totp_last_step = step
                next_url = pending.get('next')
                return _ouvrir_session(admin, next_url)
            restant = consume_backup_code(admin.backup_codes, code)
            if restant is not None:
                admin.backup_codes = restant
                next_url = pending.get('next')
                audit('code_secours_utilise', admin, cible_type='admin')
                flash(_('Code de secours utilisé. Il en reste %(n)d.', n=len(json.loads(restant))), 'warning')
                return _ouvrir_session(admin, next_url)
            _noter_tentative(admin.username, False)
            error = _('Code invalide ou déjà utilisé.')
    return render_template('admin/login_2fa.html', form=form, error=error)


@admin_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    audit('deconnexion', current_user, cible_type='admin')
    db.session.commit()
    logout_user()
    lang = session.get('lang')
    session.clear()
    if lang:
        session['lang'] = lang
    flash(_('Vous avez été déconnecté.'), 'info')
    return redirect(url_for('main_bp.index'))


# ════════════════════════════════════════════════
#  SÉCURITÉ DU COMPTE
# ════════════════════════════════════════════════

def _refresh_login(admin):
    """Après changement de version de session, garder l'admin courant connecté."""
    db.session.commit()
    login_user(admin, remember=False)


@admin_bp.route('/securite', methods=['GET'])
@login_required
def securite():
    nb_codes = len(json.loads(current_user.backup_codes)) if current_user.backup_codes else 0
    tentatives = (LoginAttempt.query.filter_by(username=current_user.username)
                  .order_by(LoginAttempt.created_at.desc()).limit(10).all())
    return render_template('admin/securite.html', pwd_form=PasswordChangeForm(),
                           disable_form=TotpDisableForm(), nb_codes=nb_codes, tentatives=tentatives)


@admin_bp.route('/securite/mot-de-passe', methods=['POST'])
@login_required
def changer_mot_de_passe():
    form = PasswordChangeForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for e in errs:
                flash(e, 'danger')
        return redirect(url_for('admin_bp.securite'))
    if not current_user.check_password(form.current_password.data):
        flash(_('Mot de passe actuel incorrect.'), 'danger')
        return redirect(url_for('admin_bp.securite'))
    problems = password_problems(form.new_password.data, current_user.username)
    if problems:
        flash(_('Mot de passe refusé : %(p)s', p=' '.join(problems)), 'danger')
        return redirect(url_for('admin_bp.securite'))
    admin = current_user._get_current_object()
    admin.set_password(form.new_password.data)
    audit('mot_de_passe_change', admin, cible_type='admin')
    _refresh_login(admin)
    flash(_('Mot de passe modifié. Toutes vos autres sessions ont été déconnectées.'), 'success')
    return redirect(url_for('admin_bp.securite'))


@admin_bp.route('/securite/2fa', methods=['GET', 'POST'])
@login_required
def activer_2fa():
    if current_user.totp_enabled:
        return redirect(url_for('admin_bp.securite'))
    secret = session.get('totp_setup')
    if not secret or request.method == 'GET':
        secret = totp_generate_secret()
        session['totp_setup'] = secret
    form = TotpSetupForm()
    if form.validate_on_submit():
        step = totp_verify(secret, form.code.data)
        if step is None:
            flash(_('Code incorrect : vérifiez l’heure de votre téléphone et réessayez.'), 'danger')
        else:
            admin = current_user._get_current_object()
            codes, hashes = generate_backup_codes()
            admin.totp_secret, admin.totp_enabled = secret, True
            admin.totp_last_step, admin.backup_codes = step, hashes
            admin.session_version = (admin.session_version or 1) + 1
            session.pop('totp_setup', None)
            audit('2fa_activee', admin, cible_type='admin')
            _refresh_login(admin)
            flash(_('Double authentification activée.'), 'success')
            return render_template('admin/codes_secours.html', codes=codes)
    uri = totp_uri(secret, current_user.username)
    return render_template('admin/2fa_setup.html', form=form, secret=secret,
                           qr_svg=Markup(totp_qr_svg(uri) or ''), uri=uri)


@admin_bp.route('/securite/2fa/desactiver', methods=['POST'])
@login_required
def desactiver_2fa():
    form = TotpDisableForm()
    if not form.validate_on_submit() or not current_user.check_password(form.password.data):
        flash(_('Mot de passe incorrect ou confirmation manquante.'), 'danger')
        return redirect(url_for('admin_bp.securite'))
    admin = current_user._get_current_object()
    admin.totp_enabled, admin.totp_secret, admin.backup_codes = False, None, None
    admin.session_version = (admin.session_version or 1) + 1
    audit('2fa_desactivee', admin, cible_type='admin')
    _refresh_login(admin)
    flash(_('Double authentification désactivée.'), 'warning')
    return redirect(url_for('admin_bp.securite'))


@admin_bp.route('/securite/codes-secours', methods=['POST'])
@login_required
def regenerer_codes():
    if not current_user.totp_enabled:
        return redirect(url_for('admin_bp.securite'))
    admin = current_user._get_current_object()
    codes, admin.backup_codes = generate_backup_codes()
    audit('codes_secours_regeneres', admin, cible_type='admin')
    db.session.commit()
    return render_template('admin/codes_secours.html', codes=codes)


# ════════════════════════════════════════════════
#  TABLEAU DE BORD ADMIN
# ════════════════════════════════════════════════

@admin_bp.route('/')
@login_required
def dashboard():
    sept_jours = _now() - timedelta(days=7)
    stats = {
        'artistes_attente':     Artiste.query.filter_by(statut='en_attente').count(),
        'artistes_approuves':   Artiste.query.filter_by(statut='approuve').count(),
        'oeuvres_attente':      Oeuvre.query.filter_by(statut='en_attente').count(),
        'oeuvres_approuvees':   Oeuvre.publiees().count(),
        'commentaires_attente': Commentaire.query.filter_by(approuve=False).count(),
        'commentaires_total':   Commentaire.query.count(),
        'signalements_nouveaux': Signalement.query.filter_by(statut='nouveau').count(),
        'profils_incomplets':   Artiste.query.filter(Artiste.profil_incomplet.is_(True),
                                                     Artiste.statut != 'rejete').count(),
        'total_likes':          Like.query.count(),
    }
    stats['total_attente'] = (stats['artistes_attente'] + stats['oeuvres_attente']
                              + stats['commentaires_attente'] + stats['signalements_nouveaux'])
    stats['soumissions_semaine'] = (
        Artiste.query.filter(Artiste.created_at >= sept_jours).count() +
        Oeuvre.query.filter(Oeuvre.created_at >= sept_jours).count() +
        Commentaire.query.filter(Commentaire.created_at >= sept_jours).count()
    )

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        artistes_attente=(Artiste.query.filter_by(statut='en_attente')
                          .order_by(Artiste.created_at.asc()).limit(10).all()),
        oeuvres_attente=(Oeuvre.query.filter_by(statut='en_attente')
                         .order_by(Oeuvre.created_at.asc()).limit(10).all()),
        commentaires_attente=(Commentaire.query.filter_by(approuve=False)
                              .order_by(Commentaire.created_at.asc()).limit(8).all()),
        signalements_recents=(Signalement.query.filter_by(statut='nouveau')
                              .order_by(Signalement.created_at.desc()).limit(6).all()),
        activite=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all(),
    )


# ════════════════════════════════════════════════
#  ARTISTES
# ════════════════════════════════════════════════

@admin_bp.route('/artistes')
@login_required
def artistes():
    statut = request.args.get('statut', 'en_attente')
    search = request.args.get('q', '').strip()[:100]

    if statut == 'incomplet':
        q = Artiste.query.filter(Artiste.profil_incomplet.is_(True), Artiste.statut != 'rejete')
    else:
        statut = statut if statut in STATUTS_VALIDES else 'en_attente'
        q = Artiste.query.filter_by(statut=statut)
    if search:
        q = q.filter(Artiste.nom.ilike(f'%{search}%'))
    counts = {s: Artiste.query.filter_by(statut=s).count() for s in STATUTS_VALIDES}
    counts['incomplet'] = Artiste.query.filter(Artiste.profil_incomplet.is_(True),
                                               Artiste.statut != 'rejete').count()
    return render_template('admin/artistes.html',
                           artistes=q.order_by(Artiste.created_at.desc()).all(),
                           statut=statut, search=search, counts=counts)


@admin_bp.route('/artiste/<int:id>')
@login_required
def artiste_detail(id):
    artiste = db.get_or_404(Artiste, id)
    oeuvres = artiste.oeuvres.order_by(Oeuvre.annee_sortie.desc()).all()
    historique = (AuditLog.query.filter_by(cible_type='artiste', cible_id=id)
                  .order_by(AuditLog.created_at.desc()).limit(30).all())
    autres = (Artiste.query.filter(Artiste.id != id, Artiste.statut != 'rejete')
              .order_by(Artiste.nom).all())
    doublons = [a for a in autres if a.nom.strip().lower() == artiste.nom.strip().lower()]
    fusion_options = doublons + [a for a in autres if a not in doublons]
    return render_template('admin/artiste_detail.html', artiste=artiste, oeuvres=oeuvres,
                           historique=historique, fusion_options=fusion_options, doublons=doublons)


def _changer_statut_artiste(artiste, action):
    """Renvoie (ok, message, catégorie)."""
    nom = artiste.nom
    if action == 'approuver':
        if artiste.profil_incomplet:
            return False, _('« %(n)s » a un profil incomplet (région / type à vérifier) : '
                            'modifiez la fiche avant de l’approuver.', n=nom), 'warning'
        artiste.statut = 'approuve'
        return True, _('Artiste « %(n)s » approuvé et publié.', n=nom), 'success'
    if action == 'rejeter':
        artiste.statut = 'rejete'
        return True, _('Artiste « %(n)s » rejeté.', n=nom), 'warning'
    if action == 'remettre_attente':
        artiste.statut = 'en_attente'
        return True, _('Artiste « %(n)s » remis en attente.', n=nom), 'info'
    return False, _('Action invalide.'), 'danger'


@admin_bp.route('/artiste/<int:id>/action/<action>', methods=['POST'])
@login_required
def action_artiste(id, action):
    artiste = db.get_or_404(Artiste, id)
    if action == 'supprimer':
        nom = artiste.nom
        audit('suppression', artiste, {'oeuvres': artiste.oeuvres.count()})
        db.session.delete(artiste)
        db.session.commit()
        flash(_('Artiste « %(n)s » supprimé définitivement.', n=nom), 'danger')
        return redirect(url_for('admin_bp.artistes'))
    avant = artiste.statut
    ok, message, cat = _changer_statut_artiste(artiste, action)
    if ok:
        audit(action, artiste, {'statut': [avant, artiste.statut]})
        db.session.commit()
    flash(message, cat)
    return retour('admin_bp.artiste_detail', id=id)


@admin_bp.route('/artiste/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def artiste_edit(id):
    artiste = db.get_or_404(Artiste, id)
    form = AdminArtisteForm(obj=artiste)
    if form.validate_on_submit():
        avant = artiste.snapshot()
        etait_incomplet = artiste.profil_incomplet
        form.populate_obj(artiste)
        artiste.profil_incomplet = False      # l'admin a vérifié la fiche
        changes = diff(avant, artiste.snapshot())
        if etait_incomplet:
            changes['profil_incomplet'] = [True, False]
        if changes:
            artiste.updated_at = _now()
            audit('modification', artiste, changes)
        message = _('Artiste « %(n)s » mis à jour.', n=artiste.nom)
        cat = 'success'
        if request.form.get('submit_action') == 'save_approve' and artiste.statut != 'approuve':
            avant_statut = artiste.statut
            artiste.statut = 'approuve'
            audit('approuver', artiste, {'statut': [avant_statut, 'approuve']})
            message = _('Artiste « %(n)s » mis à jour et publié.', n=artiste.nom)
        db.session.commit()
        flash(message, cat)
        return redirect(url_for('admin_bp.artiste_detail', id=id))
    return render_template('admin/artiste_edit.html', artiste=artiste, form=form)


@admin_bp.route('/artiste/<int:id>/fusionner', methods=['POST'])
@login_required
def fusionner_artiste(id):
    """Fusionner un doublon dans une autre fiche : œuvres, likes, commentaires,
    signalements et vues sont transférés, puis le doublon est supprimé."""
    source = db.get_or_404(Artiste, id)
    cible = db.session.get(Artiste, request.form.get('cible_id', type=int) or 0)
    if not cible or cible.id == source.id:
        flash(_('Choisissez une fiche de destination valide.'), 'danger')
        return redirect(url_for('admin_bp.artiste_detail', id=id))

    nb_oeuvres = source.oeuvres.count()
    Oeuvre.query.filter_by(artiste_id=source.id).update({'artiste_id': cible.id})
    Commentaire.query.filter_by(artiste_id=source.id).update({'artiste_id': cible.id})
    Signalement.query.filter_by(artiste_id=source.id).update({'artiste_id': cible.id})
    deja = {h for (h,) in db.session.query(Like.ip_hash).filter_by(artiste_id=cible.id)}
    for like in Like.query.filter_by(artiste_id=source.id).all():
        if like.ip_hash in deja:
            db.session.delete(like)
        else:
            like.artiste_id = cible.id
    cible.nb_vues = (cible.nb_vues or 0) + (source.nb_vues or 0)
    for champ in ('nom_reel', 'annee_debut', 'annee_fin', 'biographie', 'biographie_en',
                  'photo_url', 'site_web'):
        if not getattr(cible, champ) and getattr(source, champ):
            setattr(cible, champ, getattr(source, champ))
    audit('fusion', cible, {'fusionne_depuis': [source.id, source.nom], 'oeuvres_transferees': nb_oeuvres})
    db.session.flush()
    db.session.expire(source)
    db.session.delete(source)
    db.session.commit()
    flash(_('« %(s)s » fusionné dans « %(c)s » (%(n)d œuvre(s) transférée(s)).',
            s=source.nom, c=cible.nom, n=nb_oeuvres), 'success')
    return redirect(url_for('admin_bp.artiste_detail', id=cible.id))


# ════════════════════════════════════════════════
#  ŒUVRES
# ════════════════════════════════════════════════

@admin_bp.route('/oeuvres')
@login_required
def oeuvres():
    statut = request.args.get('statut', 'en_attente')
    statut = statut if statut in STATUTS_VALIDES else 'en_attente'
    search = request.args.get('q', '').strip()[:100]
    q = Oeuvre.query.filter_by(statut=statut)
    if search:
        q = q.filter(db.or_(Oeuvre.titre.ilike(f'%{search}%'),
                            Oeuvre.genre_musical.ilike(f'%{search}%')))
    counts = {s: Oeuvre.query.filter_by(statut=s).count() for s in STATUTS_VALIDES}
    return render_template('admin/oeuvres.html', oeuvres=q.order_by(Oeuvre.created_at.desc()).all(),
                           statut=statut, search=search, counts=counts)


@admin_bp.route('/oeuvre/<int:id>')
@login_required
def oeuvre_detail(id):
    oeuvre = db.get_or_404(Oeuvre, id)
    historique = (AuditLog.query.filter_by(cible_type='oeuvre', cible_id=id)
                  .order_by(AuditLog.created_at.desc()).limit(30).all())
    return render_template('admin/oeuvre_detail.html', oeuvre=oeuvre, historique=historique)


def _approuver_oeuvre(oeuvre):
    """Approuve l'œuvre ; publie aussi l'artiste en attente si sa fiche est complète.
    Renvoie un éventuel avertissement (artiste à compléter)."""
    oeuvre.statut = 'approuve'
    a = oeuvre.artiste
    if a and a.statut == 'en_attente':
        if a.profil_incomplet:
            return a
        a.statut = 'approuve'
        audit('approuver', a, {'statut': ['en_attente', 'approuve'], 'via_oeuvre': oeuvre.id})
    return None


def _avertir_artiste_incomplet(artiste):
    flash(Markup(_('L’œuvre restera invisible tant que l’artiste « %(n)s » n’est pas publié : '
                   'sa fiche a été créée automatiquement et doit être complétée.',
                   n=escape(artiste.nom)))
          + ' ' + lien(url_for('admin_bp.artiste_edit', id=artiste.id), _('Compléter la fiche')),
          'warning')


@admin_bp.route('/oeuvre/<int:id>/action/<action>', methods=['POST'])
@login_required
def action_oeuvre(id, action):
    oeuvre = db.get_or_404(Oeuvre, id)
    titre = oeuvre.titre
    avant = oeuvre.statut
    if action == 'supprimer':
        audit('suppression', oeuvre)
        db.session.delete(oeuvre)
        db.session.commit()
        flash(_('Œuvre « %(t)s » supprimée définitivement.', t=titre), 'danger')
        return redirect(url_for('admin_bp.oeuvres'))
    incomplet = None
    if action == 'approuver':
        incomplet = _approuver_oeuvre(oeuvre)
        flash(_('Œuvre « %(t)s » approuvée.', t=titre), 'success')
    elif action == 'rejeter':
        oeuvre.statut = 'rejete'
        flash(_('Œuvre « %(t)s » rejetée.', t=titre), 'warning')
    elif action == 'remettre_attente':
        oeuvre.statut = 'en_attente'
        flash(_('Œuvre « %(t)s » remise en attente.', t=titre), 'info')
    else:
        abort(404)
    audit(action, oeuvre, {'statut': [avant, oeuvre.statut]})
    db.session.commit()
    if incomplet:
        _avertir_artiste_incomplet(incomplet)
    return retour('admin_bp.oeuvre_detail', id=id)


def _choix_artistes(courant_id=None):
    artistes = (Artiste.query.filter(db.or_(Artiste.statut != 'rejete', Artiste.id == courant_id))
                .order_by(db.func.lower(Artiste.nom)).all())
    noms = {'approuve': '', 'en_attente': ' — ' + _('en attente'), 'rejete': ' — ' + _('rejeté')}
    return [(a.id, a.nom + noms.get(a.statut, '')) for a in artistes]


@admin_bp.route('/oeuvre/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def oeuvre_edit(id):
    oeuvre = db.get_or_404(Oeuvre, id)
    form = AdminOeuvreForm(obj=oeuvre)
    form.artiste_id.choices = _choix_artistes(oeuvre.artiste_id)
    if form.validate_on_submit():
        avant = oeuvre.snapshot()
        form.populate_obj(oeuvre)
        changes = diff(avant, oeuvre.snapshot())
        if 'artiste_id' in changes:
            noms = dict(form.artiste_id.choices)
            changes['artiste_id'] = [noms.get(v, v) for v in changes['artiste_id']]
        if changes:
            oeuvre.updated_at = _now()
            audit('modification', oeuvre, changes)
        db.session.flush()
        db.session.refresh(oeuvre)
        incomplet = None
        message = _('Œuvre « %(t)s » mise à jour.', t=oeuvre.titre)
        if request.form.get('submit_action') == 'save_approve' and oeuvre.statut != 'approuve':
            avant_statut = oeuvre.statut
            incomplet = _approuver_oeuvre(oeuvre)
            audit('approuver', oeuvre, {'statut': [avant_statut, 'approuve']})
            message = _('Œuvre « %(t)s » mise à jour et approuvée.', t=oeuvre.titre)
        db.session.commit()
        flash(message, 'success')
        if incomplet:
            _avertir_artiste_incomplet(incomplet)
        return redirect(url_for('admin_bp.oeuvre_detail', id=id))
    return render_template('admin/oeuvre_edit.html', oeuvre=oeuvre, form=form)


# ════════════════════════════════════════════════
#  ACTIONS EN LOT
# ════════════════════════════════════════════════

@admin_bp.route('/bulk', methods=['POST'])
@login_required
def bulk_action():
    action     = request.form.get('action')
    model_type = request.form.get('model')
    ids = [int(i) for i in request.form.getlist('ids') if i.isdigit()]

    if not ids or action not in ('approuver', 'rejeter', 'supprimer') or model_type not in ('artiste', 'oeuvre'):
        flash(_('Action invalide.'), 'danger')
        return retour('admin_bp.dashboard')

    Model = Artiste if model_type == 'artiste' else Oeuvre
    count, ignores, incomplets = 0, 0, set()
    for item in Model.query.filter(Model.id.in_(ids)).all():
        if action == 'supprimer':
            audit('suppression', item)
            db.session.delete(item)
        elif action == 'rejeter':
            audit('rejeter', item, {'statut': [item.statut, 'rejete']})
            item.statut = 'rejete'
        elif model_type == 'artiste':
            avant = item.statut
            ok, _m, _c = _changer_statut_artiste(item, 'approuver')
            if not ok:
                ignores += 1
                continue
            audit('approuver', item, {'statut': [avant, 'approuve']})
        else:
            avant = item.statut
            a = _approuver_oeuvre(item)
            if a:
                incomplets.add(a)
            audit('approuver', item, {'statut': [avant, 'approuve']})
        count += 1
    db.session.commit()
    flash(_('%(n)d entrée(s) traitée(s).', n=count), 'success')
    if ignores:
        flash(_('%(n)d artiste(s) ignoré(s) : profil incomplet à compléter d’abord.', n=ignores), 'warning')
    for a in incomplets:
        _avertir_artiste_incomplet(a)
    return retour('admin_bp.dashboard')


# ════════════════════════════════════════════════
#  EXPORT CSV (admin : inclut les contributeurs)
# ════════════════════════════════════════════════

@admin_bp.route('/export/oeuvres.csv')
@login_required
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([_('ID'), _('Titre'), _('Artiste'), _('Région'), _('Type'), _('Genre'), _('Langue'),
                     _('Année'), _('Décennie'), _('Popularité'), _('Distinction'), _('Lien YouTube'),
                     _('Statut'), _('Soumis par'), _('Email')])
    for o in Oeuvre.query.order_by(Oeuvre.annee_sortie).all():
        writer.writerow([csv_safe(v) for v in (
            o.id, o.titre, o.artiste.nom if o.artiste else '',
            o.artiste.region_origine if o.artiste else '', o.type_oeuvre, o.genre_musical,
            o.langue, o.annee_sortie, o.decennie or '', o.popularite or '', o.distinction or '',
            o.lien_youtube or '', o.statut, o.soumis_par or '', o.soumis_email or '')])
    audit('export_csv', cible_type='oeuvre')
    db.session.commit()
    return Response('﻿' + output.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename=jackbeat_admin.csv'})


@admin_bp.route('/api/summary')
@login_required
def api_summary():
    return jsonify({
        'artistes': {s: Artiste.query.filter_by(statut=s).count() for s in STATUTS_VALIDES},
        'oeuvres': {s: Oeuvre.query.filter_by(statut=s).count() for s in STATUTS_VALIDES},
        'timestamp': _now().isoformat(),
    })


# ════════════════════════════════════════════════
#  COMMENTAIRES — MODÉRATION
# ════════════════════════════════════════════════

@admin_bp.route('/commentaires')
@login_required
def commentaires():
    filtre = request.args.get('statut', 'attente')
    if filtre == 'attente':
        q = Commentaire.query.filter_by(approuve=False)
    elif filtre == 'approuves':
        q = Commentaire.query.filter_by(approuve=True)
    else:
        filtre, q = 'tous', Commentaire.query
    counts = {
        'attente':   Commentaire.query.filter_by(approuve=False).count(),
        'approuves': Commentaire.query.filter_by(approuve=True).count(),
        'tous':      Commentaire.query.count(),
    }
    return render_template('admin/commentaires.html',
                           comments=q.order_by(Commentaire.created_at.desc()).all(),
                           statut_filtre=filtre, counts=counts)


@admin_bp.route('/commentaire/<int:id>/action/<action>', methods=['POST'])
@login_required
def action_commentaire(id, action):
    c = db.get_or_404(Commentaire, id)
    if action == 'approuver':
        c.approuve = True
        audit('approuver', cible_type='commentaire', details={'auteur': c.auteur, 'id': c.id})
        flash(_('Commentaire de « %(a)s » approuvé.', a=c.auteur), 'success')
    elif action == 'rejeter':
        audit('suppression', cible_type='commentaire', details={'auteur': c.auteur, 'texte': c.texte[:200]})
        db.session.delete(c)
        flash(_('Commentaire supprimé.'), 'warning')
    else:
        abort(404)
    db.session.commit()
    return retour('admin_bp.commentaires')


@admin_bp.route('/commentaires/bulk', methods=['POST'])
@login_required
def commentaires_bulk():
    action = request.form.get('action')
    ids = [int(i) for i in request.form.getlist('ids') if i.isdigit()]
    if not ids or action not in ('approuver', 'supprimer'):
        flash(_('Aucune sélection.'), 'warning')
        return redirect(url_for('admin_bp.commentaires'))
    items = Commentaire.query.filter(Commentaire.id.in_(ids)).all()
    for c in items:
        if action == 'approuver':
            c.approuve = True
        else:
            db.session.delete(c)
    audit(f'commentaires_{action}', cible_type='commentaire', details={'ids': ids})
    db.session.commit()
    flash(_('%(n)d commentaire(s) traité(s).', n=len(items)), 'success')
    return redirect(url_for('admin_bp.commentaires'))


# ════════════════════════════════════════════════
#  SIGNALEMENTS
# ════════════════════════════════════════════════

@admin_bp.route('/signalements')
@login_required
def signalements():
    statut = request.args.get('statut', 'nouveau')
    q = Signalement.query
    if statut != 'tous':
        statut = statut if statut in ('nouveau', 'en_cours', 'resolu', 'rejete') else 'nouveau'
        q = q.filter_by(statut=statut)
    counts = {s: Signalement.query.filter_by(statut=s).count()
              for s in ('nouveau', 'en_cours', 'resolu', 'rejete')}
    counts['tous'] = sum(counts.values())
    return render_template('admin/signalements.html',
                           signalements=q.order_by(Signalement.created_at.desc()).all(),
                           statut_filtre=statut, counts=counts)


@admin_bp.route('/signalement/<int:id>/statut', methods=['POST'])
@login_required
def signalement_statut(id):
    s = db.get_or_404(Signalement, id)
    nouveau_statut = request.form.get('statut')
    note = request.form.get('note_admin', '').strip()[:2000]
    avant = s.statut
    if nouveau_statut in ('nouveau', 'en_cours', 'resolu', 'rejete'):
        s.statut = nouveau_statut
    s.note_admin = note or None
    audit('signalement', cible_type='signalement',
          details={'id': s.id, 'statut': [avant, s.statut], 'cible': s.cible_nom})
    db.session.commit()
    flash(_('Signalement mis à jour : %(s)s.', s=libelle('statut_signalement', s.statut)), 'success')
    return retour('admin_bp.signalements')


# ════════════════════════════════════════════════
#  JOURNAL D'AUDIT
# ════════════════════════════════════════════════

@admin_bp.route('/journal')
@login_required
def journal():
    page = request.args.get('page', 1, type=int)
    cible = request.args.get('cible', '')
    q = AuditLog.query
    if cible in ('artiste', 'oeuvre', 'commentaire', 'signalement', 'admin'):
        q = q.filter_by(cible_type=cible)
    entrees = q.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=40, error_out=False)
    return render_template('admin/journal.html', entrees=entrees, cible=cible)
