import re

from flask import request, current_app
from flask_socketio import emit, join_room, leave_room

from .. import socketio
from ..models import db, Message


def _sanitize_text(text, max_len=500):
    """Strip control chars, collapse whitespace, enforce length."""
    if not text:
        return ""
    # Remove null bytes and control characters (keep newlines/tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Collapse excessive whitespace/newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {3,}', '  ', text)
    return text.strip()[:max_len]


_RESERVED_NAMES = {
    "admin", "system", "moderator", "outpost", "server",
    "administrator", "mod", "operator", "staff",
}

def _sanitize_username(name):
    """Clean username: alphanumeric + basic punctuation only, 32 char max."""
    if not name:
        return ""
    # Strip HTML tags
    name = re.sub(r'<[^>]+>', '', name)
    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    # Only allow letters, numbers, spaces, underscores, hyphens, periods
    name = re.sub(r'[^\w\s.\-]', '', name, flags=re.UNICODE)
    name = name.strip()
    if not name:
        return "anon"
    name = name[:32]
    # Block impersonation of privileged names
    if name.lower() in _RESERVED_NAMES:
        name = f"[{name}]"
    return name

# In-memory client registry: sid -> {username, channel}
_clients: dict[str, dict] = {}


def _user_count() -> int:
    # Only count connections that have joined with a username
    return sum(1 for c in _clients.values() if c.get("username"))


def _broadcast_user_count():
    socketio.emit("user_count", {"count": _user_count()})


def _channel_history(channel: str, limit: int = 50):
    msgs = (
        Message.query
        .filter_by(channel=channel, deleted=False)
        .order_by(Message.id.desc())
        .limit(limit)
        .all()
    )
    return [m.to_dict() for m in reversed(msgs)]


@socketio.on("connect")
def on_connect():
    sid = request.sid
    # Just register the SID. Don't send history here — the client always
    # emits 'join' on connect, which will handle history + user_count.
    # Sending history here AND from on_join causes a race where the second
    # history event overwrites messages that arrived in between.
    _clients[sid] = {"username": None, "channel": "pitwall"}
    join_room("pitwall", sid=sid)


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    client = _clients.pop(sid, None)
    # Only broadcast if this was an identified user (had a username)
    if client and client.get("username"):
        _broadcast_user_count()


@socketio.on("join")
def on_join(data):
    sid = request.sid
    username = (data or {}).get("username") or "anon"
    channel = (data or {}).get("channel") or "pitwall"
    allowed = current_app.config.get("CHAT_CHANNELS", ["pitwall", "ctf"])
    if channel not in allowed:
        channel = "pitwall"
    state = _clients.setdefault(sid, {"username": None, "channel": "pitwall"})
    # leave old channel
    if state.get("channel") and state["channel"] != channel:
        leave_room(state["channel"], sid=sid)
    join_room(channel, sid=sid)
    state["username"] = _sanitize_username(username)
    state["channel"] = channel
    emit("history", {"channel": channel, "messages": _channel_history(channel)})
    _broadcast_user_count()


@socketio.on("message")
def on_message(data):
    sid = request.sid
    state = _clients.get(sid)
    if not state or not state.get("username"):
        emit("error", {"error": "join first with {username, channel}"})
        return
    body = _sanitize_text((data or {}).get("body") or "", max_len=500)
    if not body:
        return
    msg = Message(username=state["username"], channel=state["channel"], body=body)
    db.session.add(msg)
    db.session.commit()
    socketio.emit("message", msg.to_dict(), to=state["channel"])


@socketio.on("delete_message")
def on_delete_message(data):
    # Admin-only: requires a shared admin token from config
    token = (data or {}).get("admin_token", "")
    if token != current_app.config.get("ADMIN_PASSWORD"):
        emit("error", {"error": "unauthorized"})
        return
    mid = (data or {}).get("message_id")
    msg = Message.query.get(mid) if mid else None
    if not msg:
        return
    msg.deleted = True
    db.session.commit()
    socketio.emit("message_deleted", {"id": msg.id, "channel": msg.channel}, to=msg.channel)
