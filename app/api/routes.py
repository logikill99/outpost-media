import json
import os
import time
from flask import Blueprint, jsonify, current_app, request

from ..models import Announcement

bp = Blueprint("api", __name__)

VALID_STANDINGS_SERIES = {"f1", "f2", "porsche", "mclaren"}


def _standings_path(series):
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "content", "standings", f"{series}.json",
    )


@bp.route("/api/status")
def status():
    from ..chat.events import _clients
    import app as _app_module
    start = current_app.config.get("START_TIME", time.time())
    active = Announcement.query.filter_by(active=True).all()
    return jsonify({
        "connected_clients": len(_clients),
        "page_hits": getattr(_app_module, '_page_hits', 0),
        "uptime_seconds": int(time.time() - start),
        "active_announcements": [a.to_dict() for a in active],
    })


# Hidden CTF challenge endpoint — "Pit Wall Intercept"
@bp.route("/api/_debug")
def debug_endpoint():
    return jsonify({
        "service": "outpost-radio",
        "build": "0xdeadbeef",
        "note": "FLAG{radio_check_one_two_one_two}",
    })


@bp.route("/api/standings/<series>", methods=["GET"])
def get_standings(series):
    series = series.lower()
    if series not in VALID_STANDINGS_SERIES:
        return jsonify({"error": "unknown series"}), 404
    try:
        with open(_standings_path(series)) as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"error": "standings not yet available"}), 404


@bp.route("/api/standings/<series>", methods=["PUT"])
def put_standings(series):
    series = series.lower()
    if series not in VALID_STANDINGS_SERIES:
        return jsonify({"error": "unknown series"}), 404

    payload = request.get_json(silent=True) or {}
    token = payload.get("admin_token")
    data = payload.get("data")
    if token != current_app.config.get("ADMIN_PASSWORD"):
        return jsonify({"error": "unauthorized"}), 401
    if not isinstance(data, dict):
        return jsonify({"error": "invalid data — expected object"}), 400

    path = _standings_path(series)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return jsonify({"ok": True, "series": series, "bytes": os.path.getsize(path)})
