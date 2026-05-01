import hashlib
import re
from collections import defaultdict
from flask import Blueprint, jsonify, request, render_template

from ..models import db, Challenge, Solve, Announcement


_CTF_RESERVED = {
    "admin", "system", "moderator", "outpost", "server",
    "administrator", "mod", "operator", "staff",
}

def _clean_username(name):
    if not name:
        return ""
    name = re.sub(r'<[^>]+>', '', name)
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    name = re.sub(r'[^\w\s.\-]', '', name, flags=re.UNICODE)
    name = name.strip()[:32] or "anon"
    if name.lower() in _CTF_RESERVED:
        name = f"[{name}]"
    return name

bp = Blueprint("ctf", __name__)


@bp.route("/ctf/")
def ctf_index():
    active = Announcement.query.filter_by(active=True).all()
    return render_template("ctf/index.html", announcements=[a.to_dict() for a in active])


@bp.route("/ctf/<slug>")
def ctf_challenge(slug):
    chal = Challenge.query.filter_by(slug=slug, active=True).first_or_404()
    active = Announcement.query.filter_by(active=True).all()
    return render_template(
        "ctf/challenge.html",
        challenge=chal.to_public_dict(),
        announcements=[a.to_dict() for a in active],
    )


@bp.route("/api/ctf/challenges", methods=["GET"])
def api_challenges():
    # Sort by id to get a stable order that matches the stored Final Lap answer
    chals = Challenge.query.filter_by(active=True).order_by(Challenge.id.asc()).all()
    return jsonify([c.to_public_dict() for c in chals])


@bp.route("/api/ctf/submit", methods=["POST"])
def api_submit():
    data = request.get_json(silent=True) or {}
    username = _clean_username(data.get("username") or "")
    slug = (data.get("slug") or "").strip()
    flag = (data.get("flag") or "").strip()
    if not username or not slug or not flag:
        return jsonify({"correct": False, "points": 0,
                        "message": "Missing username, slug, or flag."}), 400

    chal = Challenge.query.filter_by(slug=slug, active=True).first()
    if not chal:
        return jsonify({"correct": False, "points": 0,
                        "message": "Challenge not found."}), 404

    submitted_hash = hashlib.sha256(flag.encode()).hexdigest()
    if submitted_hash != chal.flag_hash:
        return jsonify({"correct": False, "points": 0,
                        "message": "Incorrect flag. Keep trying."})

    existing = Solve.query.filter_by(username=username, challenge_id=chal.id).first()
    if existing:
        return jsonify({"correct": True, "points": chal.points,
                        "message": "Correct, but you already solved this one."})

    solve = Solve(username=username, challenge_id=chal.id)
    db.session.add(solve)
    db.session.commit()
    return jsonify({"correct": True, "points": chal.points,
                    "message": f"Correct! +{chal.points} points."})


@bp.route("/api/ctf/leaderboard", methods=["GET"])
def api_leaderboard():
    rows = (
        db.session.query(Solve.username, Challenge.points)
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .all()
    )
    score = defaultdict(int)
    solves = defaultdict(int)
    for username, points in rows:
        score[username] += points
        solves[username] += 1
    board = [
        {"username": u, "score": score[u], "solves": solves[u]}
        for u in score
    ]
    board.sort(key=lambda x: (-x["score"], -x["solves"], x["username"]))
    return jsonify(board)
