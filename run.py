"""Entry point. Run: python run.py"""
import eventlet
eventlet.monkey_patch()

import os  # noqa: E402

from app import create_app, socketio  # noqa: E402

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
