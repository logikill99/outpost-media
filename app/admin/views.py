import hashlib
from functools import wraps
from flask import request, Response, redirect, url_for, flash
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.actions import action
from flask_admin.contrib.sqla import ModelView

from .. import socketio
from ..models import db, Message, Challenge, Solve, Announcement


def _check_auth(username: str, password: str, expected_password: str) -> bool:
    return password == expected_password


def _authenticate():
    return Response(
        "Auth required.\n", 401,
        {"WWW-Authenticate": 'Basic realm="Outpost Admin"'},
    )


def basic_auth_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        from flask import current_app
        expected = current_app.config["ADMIN_PASSWORD"]
        auth = request.authorization
        if not auth or not _check_auth(auth.username, auth.password, expected):
            return _authenticate()
        return f(*args, **kwargs)
    return wrapped


class AuthMixin:
    def is_accessible(self):
        from flask import current_app
        expected = current_app.config["ADMIN_PASSWORD"]
        auth = request.authorization
        return bool(auth and _check_auth(auth.username, auth.password, expected))

    def inaccessible_callback(self, name, **kwargs):
        return _authenticate()


class OutpostIndexView(AuthMixin, AdminIndexView):
    @expose("/")
    def index(self):
        from ..models import Message, Challenge, Solve, Announcement
        stats = {
            "messages": Message.query.count(),
            "challenges": Challenge.query.count(),
            "solves": Solve.query.count(),
            "announcements_active": Announcement.query.filter_by(active=True).count(),
        }
        return self.render("admin/outpost_index.html", stats=stats)


class ChallengeAdmin(AuthMixin, ModelView):
    column_list = ("id", "slug", "title", "category", "points", "active", "flag_hash")
    column_searchable_list = ("slug", "title", "category")
    column_filters = ("category", "active")
    form_columns = ("slug", "title", "description", "category", "points", "flag_hash", "active", "hint")
    can_create = True
    can_edit = True
    can_delete = True

    def on_model_change(self, form, model, is_created):
        # If admin pasted a plaintext flag (looks like FLAG{...}), hash it.
        val = (model.flag_hash or "").strip()
        if val.startswith("FLAG{") and val.endswith("}"):
            model.flag_hash = hashlib.sha256(val.encode()).hexdigest()


class MessageAdmin(AuthMixin, ModelView):
    column_list = ("id", "username", "channel", "body", "created_at", "deleted")
    column_filters = ("channel", "deleted", "username")
    column_default_sort = ("id", True)
    can_create = False
    can_edit = False
    can_delete = True

    def get_query(self):
        return super().get_query()


class AnnouncementAdmin(AuthMixin, ModelView):
    column_list = ("id", "body", "active", "created_at")
    form_columns = ("body", "active")
    can_create = True
    can_edit = True
    can_delete = True

    def _emit(self, model):
        try:
            socketio.emit("announcement", {
                "id": model.id, "body": model.body, "active": model.active,
            })
        except Exception:
            pass

    def after_model_change(self, form, model, is_created):
        if model.active:
            self._emit(model)


class SolveAdmin(AuthMixin, ModelView):
    column_list = ("id", "username", "challenge_id", "solved_at")
    column_filters = ("username",)
    column_default_sort = ("solved_at", True)
    can_create = False
    can_edit = False
    can_delete = True

    @action("reset_leaderboard", "Reset leaderboard",
            "Are you sure? This deletes ALL solve records.")
    def action_reset_leaderboard(self, ids):
        try:
            Solve.query.delete()
            db.session.commit()
            flash("Leaderboard reset — all solves deleted.")
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            flash(f"Failed to reset: {e}", "error")
        return redirect(url_for(".index_view"))


def init_admin(app):
    admin = Admin(
        app,
        name="Outpost Admin",
        index_view=OutpostIndexView(name="Home", url="/admin"),
        url="/admin",
    )
    admin.add_view(ChallengeAdmin(Challenge, db.session, name="Challenges"))
    admin.add_view(MessageAdmin(Message, db.session, name="Messages"))
    admin.add_view(AnnouncementAdmin(Announcement, db.session, name="Announcements"))
    admin.add_view(SolveAdmin(Solve, db.session, name="Solves"))
