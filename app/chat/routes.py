from flask import Blueprint, render_template
from ..models import Announcement

bp = Blueprint("chat", __name__)


@bp.route("/chat")
def chat_page():
    active = Announcement.query.filter_by(active=True).all()
    return render_template("chat.html", announcements=[a.to_dict() for a in active])
