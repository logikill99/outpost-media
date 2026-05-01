import json
import os
import time
from datetime import datetime, timezone

from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO

from .config import Config
from .models import db, Message, Challenge, Solve, Announcement

socketio = SocketIO(async_mode="eventlet", cors_allowed_origins="*")
START_TIME = time.time()
_page_hits = 0


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class)
    app.config["START_TIME"] = START_TIME

    db.init_app(app)
    socketio.init_app(app, message_queue=None)

    # Enable SQLite WAL mode + busy timeout for concurrent event-day load
    from sqlalchemy import event as sa_event
    from sqlalchemy.engine import Engine
    import sqlite3
    @sa_event.listens_for(Engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _rec):
        if isinstance(dbapi_conn, sqlite3.Connection):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

    from .chat import events as chat_events  # noqa: F401 — registers handlers
    from .ctf.routes import bp as ctf_bp
    from .api.routes import bp as api_bp
    from .chat.routes import bp as chat_bp

    app.register_blueprint(ctf_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(chat_bp)

    from .admin.views import init_admin
    init_admin(app)

    @app.route("/")
    def index():
        active = Announcement.query.filter_by(active=True).all()
        return render_template("index.html", announcements=[a.to_dict() for a in active])

    @app.route("/movies")
    def movies():
        # Auto-discover video files in media/videos/
        videos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media", "videos")
        
        # Load optional metadata from movies.json (_load_json now handles errors internally)
        meta_list = _load_json("../movies.json") or []  # content/movies.json
        meta_by_file = {m["filename"]: m for m in meta_list if "filename" in m}
        
        # Scan directory for .mp4 files
        movie_list = []
        if os.path.isdir(videos_dir):
            for f in sorted(os.listdir(videos_dir)):
                if f.lower().endswith(('.mp4', '.mkv', '.webm')):
                    if f in meta_by_file:
                        movie_list.append(meta_by_file[f])
                    else:
                        # Generate metadata from filename
                        name = os.path.splitext(f)[0]
                        title = name.replace('-', ' ').replace('_', ' ').title()
                        size_mb = os.path.getsize(os.path.join(videos_dir, f)) / (1024*1024)
                        movie_list.append({
                            "title": title,
                            "filename": f,
                            "year": "",
                            "duration": f"{size_mb:.0f} MB",
                            "description": "",
                            "genre": "Unknown"
                        })
        
        return render_template("movies.html", movies=movie_list, announcements=_announcements())

    @app.route("/games")
    def games():
        active = Announcement.query.filter_by(active=True).all()
        return render_template("games.html", announcements=[a.to_dict() for a in active])

    @app.route("/library")
    def library():
        active = Announcement.query.filter_by(active=True).all()
        return render_template("library.html", announcements=[a.to_dict() for a in active])

    # In-memory content cache — data is static all weekend
    _cache: dict = {}
    _CACHE_TTL = 300  # seconds

    def _cache_get(key):
        entry = _cache.get(key)
        if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
            return entry["data"], True
        return None, False

    def _cache_set(key, data):
        _cache[key] = {"data": data, "ts": time.time()}

    def _load_json(filename, default=None):
        cached, hit = _cache_get(f"json:{filename}")
        if hit:
            return cached
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content", "f1data", filename)
        try:
            with open(path) as f:
                data = json.load(f)
            _cache_set(f"json:{filename}", data)
            return data
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            app.logger.warning(f"_load_json({filename}) failed: {e}")
            return default

    def _load_standings(series):
        cached, hit = _cache_get(f"standings:{series}")
        if hit:
            return cached
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content", "standings", f"{series}.json")
        try:
            with open(path) as f:
                data = json.load(f)
            _cache_set(f"standings:{series}", data)
            return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _announcements():
        return [a.to_dict() for a in Announcement.query.filter_by(active=True).all()]

    def _driver_standings_by_slug(drivers, standings_drivers):
        """Match drivers.json entries to standings rows by surname (handles 'Kimi
        Antonelli' vs 'Andrea Kimi Antonelli'). Returns {drivers.json slug: row}."""
        out = {}
        for d in drivers:
            surname = (d.get("name") or "").split()[-1].lower()
            if not surname:
                continue
            for s in standings_drivers or []:
                sname = (s.get("driver") or s.get("name") or "").lower()
                if sname == (d.get("name") or "").lower() or sname.endswith(surname):
                    out[d["slug"]] = s
                    break
        return out

    # ── Schedule (top-level) ────────────────────────
    @app.route("/schedule")
    def schedule_page():
        schedule = _load_json("schedule.json") or {}
        # Set active tab based on local event date (UTC-4)
        from datetime import timedelta
        miami_now = datetime.now(timezone.utc) - timedelta(hours=4)
        day_map = {1: "Friday", 2: "Saturday", 3: "Sunday"}
        active_day = day_map.get(miami_now.day if miami_now.month == 5 and miami_now.year == 2026 else None, "Friday")
        return render_template("schedule.html", schedule=schedule, active_day=active_day, announcements=_announcements())

    # ── /info hub ───────────────────────────────────
    @app.route("/info")
    @app.route("/info/")
    def info_index():
        leaders = {}
        for series in ("f1", "f2", "mclaren"):
            data = _load_standings(series)
            if data and data.get("drivers"):
                top = data["drivers"][0]
                leaders[series] = {
                    "name": top.get("driver") or top.get("name"),
                    "points": top.get("points"),
                    "team": top.get("team"),
                }
        # Porsche has class-grouped standings under .standings[*].standings
        porsche = _load_standings("porsche")
        if porsche and porsche.get("standings"):
            pro = next((g for g in porsche["standings"] if g.get("class") == "Pro"), None)
            if pro and pro.get("standings"):
                top = pro["standings"][0]
                leaders["porsche"] = {
                    "name": top.get("driver"),
                    "points": top.get("total_points"),
                    "team": "Pro class",
                }
        return render_template("info/index.html", leaders=leaders, announcements=_announcements())

    # ── /info/f1/* ──────────────────────────────────
    @app.route("/info/f1/drivers")
    def info_f1_drivers():
        drivers = _load_json("drivers.json") or []
        standings = _load_standings("f1") or {"drivers": []}
        race_results = _load_json("race_results_2026.json") or []
        sprint_results = _load_json("sprint_results_2026.json") or []
        standings_by_slug = _driver_standings_by_slug(drivers, standings.get("drivers", []))
        return render_template(
            "info/f1/drivers.html",
            drivers=drivers,
            standings=standings,
            standings_by_slug=standings_by_slug,
            race_results=race_results,
            sprint_results=sprint_results,
            announcements=_announcements(),
        )

    @app.route("/info/f1/teams")
    def info_f1_teams():
        teams = _load_json("teams.json") or []
        standings = _load_standings("f1") or {"drivers": [], "constructors": []}
        return render_template(
            "info/f1/teams.html",
            teams=teams,
            standings=standings,
            announcements=_announcements(),
        )

    @app.route("/info/f1/general")
    def info_f1_general():
        schedule = _load_json("schedule.json") or {}
        race_results = _load_json("race_results_2026.json") or []
        sprint_results = _load_json("sprint_results_2026.json") or []
        miami_history = _load_json("miami_history.json") or {}
        standings = _load_standings("f1") or {"drivers": [], "constructors": []}
        return render_template(
            "info/f1/general.html",
            schedule=schedule,
            race_results=race_results,
            sprint_results=sprint_results,
            miami_history=miami_history,
            standings=standings,
            announcements=_announcements(),
        )

    # ── /info/f2/* ──────────────────────────────────
    @app.route("/info/f2/drivers")
    def info_f2_drivers():
        drivers = _load_json("f2_drivers.json") or []
        standings = _load_standings("f2") or {"drivers": [], "teams": []}
        results = _load_json("f2_results_2026.json") or []
        return render_template(
            "info/f2/drivers.html",
            drivers=drivers,
            standings=standings,
            results=results,
            announcements=_announcements(),
        )

    @app.route("/info/f2/teams")
    def info_f2_teams():
        teams = _load_json("f2_teams.json") or []
        standings = _load_standings("f2") or {"drivers": [], "teams": []}
        return render_template(
            "info/f2/teams.html",
            teams=teams,
            standings=standings,
            announcements=_announcements(),
        )

    @app.route("/info/f2/general")
    def info_f2_general():
        standings = _load_standings("f2") or {"drivers": [], "teams": []}
        results = _load_json("f2_results_2026.json") or []
        return render_template(
            "info/f2/general.html",
            standings=standings,
            results=results,
            announcements=_announcements(),
        )

    # ── /info/porsche/* ─────────────────────────────
    @app.route("/info/porsche/drivers")
    def info_porsche_drivers():
        drivers = _load_json("porsche_drivers.json") or []
        standings = _load_standings("porsche") or {"standings": []}
        results = _load_json("porsche_results_2026.json") or []
        return render_template(
            "info/porsche/drivers.html",
            drivers=drivers,
            standings=standings,
            results=results,
            announcements=_announcements(),
        )

    @app.route("/info/porsche/teams")
    def info_porsche_teams():
        teams = _load_json("porsche_teams.json") or []
        standings = _load_standings("porsche") or {"standings": []}
        return render_template(
            "info/porsche/teams.html",
            teams=teams,
            standings=standings,
            announcements=_announcements(),
        )

    @app.route("/info/porsche/general")
    def info_porsche_general():
        standings = _load_standings("porsche") or {"standings": []}
        results = _load_json("porsche_results_2026.json") or []
        return render_template(
            "info/porsche/general.html",
            standings=standings,
            results=results,
            announcements=_announcements(),
        )

    # ── /info/mclaren/* ─────────────────────────────
    @app.route("/info/mclaren/drivers")
    def info_mclaren_drivers():
        drivers = _load_json("mclaren_drivers.json") or []
        standings = _load_standings("mclaren") or {}
        results = _load_json("mclaren_results_2026.json") or []
        return render_template(
            "info/mclaren/drivers.html",
            drivers=drivers,
            standings=standings,
            results=results,
            announcements=_announcements(),
        )

    @app.route("/info/mclaren/teams")
    def info_mclaren_teams():
        teams = _load_json("mclaren_teams.json") or []
        standings = _load_standings("mclaren") or {}
        return render_template("info/mclaren/teams.html", teams=teams, standings=standings, announcements=_announcements())

    @app.route("/info/mclaren/general")
    def info_mclaren_general():
        results = _load_json("mclaren_results_2026.json") or []
        standings = _load_standings("mclaren") or {}
        return render_template(
            "info/mclaren/general.html",
            results=results,
            standings=standings,
            announcements=_announcements(),
        )

    # ── Backward-compat redirects from old /f1/* routes ──
    from flask import redirect
    @app.route("/f1/")
    @app.route("/f1")
    def f1_index_redirect():
        return redirect("/info", code=301)

    @app.route("/f1/drivers")
    def f1_drivers_redirect():
        return redirect("/info/f1/drivers", code=301)

    @app.route("/f1/teams")
    def f1_teams_redirect():
        return redirect("/info/f1/teams", code=301)

    @app.route("/f1/track")
    def f1_track_redirect():
        return redirect("/info/f1/general", code=301)

    @app.route("/f1/schedule")
    def f1_schedule_redirect():
        return redirect("/schedule", code=301)

    @app.route("/f1/support")
    def f1_support_redirect():
        return redirect("/info", code=301)

    @app.route("/about")
    def about():
        return render_template("about.html", announcements=_announcements())

    @app.route("/portal")
    def portal():
        return render_template("portal.html")

    @app.route("/content/<path:filename>")
    def content_files(filename):
        content_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "content")
        return send_from_directory(content_dir, filename)

    @app.route("/media/videos/<path:filename>")
    def media_videos(filename):
        media_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media", "videos")
        return send_from_directory(media_dir, filename, conditional=True)

    # Captive-portal probe targets — redirect to /portal so the OS opens the CNA
    @app.route("/hotspot-detect.html")
    @app.route("/library/test/success.html")
    @app.route("/generate_204")
    @app.route("/gen_204")
    @app.route("/ncsi.txt")
    @app.route("/connecttest.txt")
    @app.route("/redirect")
    def captive_probe():
        from flask import redirect
        return redirect("/portal", code=302)

    @app.before_request
    def _count_hit():
        global _page_hits
        from flask import request
        # Count only HTML page requests, not API/static/socket calls
        path = request.path
        if not any(path.startswith(p) for p in ('/api/', '/static/', '/content/', '/socket.io/', '/media/')):
            _page_hits += 1

    with app.app_context():
        db.create_all()
        _seed_initial_data(app)

    return app


def _seed_initial_data(app):
    """Seed CTF challenges + sample announcement on first run if DB is empty."""
    import hashlib
    if Challenge.query.count() == 0:
        seeds = [
            ("welcome-paddock", "Welcome to the Paddock", "misc", 50,
             "Somewhere on this site is your first flag. Try viewing the page source.",
             app.config["CTF_FLAGS"].get("welcome-paddock", "FLAG{placeholder}"),
             "Right-click → View Source. Look for HTML comments."),
            ("pit-wall-intercept", "Pit Wall Intercept", "web", 100,
             "Our radio engineer left a debug endpoint exposed under /api somewhere. Find it.",
             app.config["CTF_FLAGS"].get("pit-wall-intercept", "FLAG{placeholder}"),
             "Try /api/_debug or watch network requests."),
            ("steg-lap", "Steganography Lap", "steg", 150,
             "An image hides a flag in plain sight. Look at the LSBs.",
             app.config["CTF_FLAGS"].get("steg-lap", "FLAG{placeholder}"),
             "Tools like steghide or zsteg can help. Or look at file metadata."),
            ("caesars-pit-stop", "Caesar's Pit Stop", "cipher", 100,
             "SYNT{ebgngrq_guvegrra_cynprf} — what does it say?",
             app.config["CTF_FLAGS"].get("caesars-pit-stop", "FLAG{placeholder}"),
             "ROT13 is your friend."),
            ("black-box", "Black Box", "forensics", 200,
             "A telemetry log file was leaked. The flag is in the metadata.",
             app.config["CTF_FLAGS"].get("black-box", "FLAG{placeholder}"),
             "exiftool or strings."),
            ("final-lap", "Final Lap", "misc", 300,
             "Combine the first letter of each previous flag's content, in the order they appear on this page (top to bottom). Wrap in FLAG{}.",
             app.config["CTF_FLAGS"].get("final-lap", "FLAG{placeholder}"),
             "Solve the others first. There are 5 flags before this one."),
        ]
        for slug, title, cat, pts, desc, flag, hint in seeds:
            db.session.add(Challenge(
                slug=slug, title=title, category=cat, points=pts,
                description=desc,
                flag_hash=hashlib.sha256(flag.encode()).hexdigest(),
                hint=hint, active=True,
            ))
        db.session.commit()

    if Announcement.query.count() == 0:
        db.session.add(Announcement(
            body="Welcome to Outpost. Try the chat, play the CTF, watch a movie.",
            active=True,
        ))
        db.session.commit()
