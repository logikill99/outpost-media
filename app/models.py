from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Message(db.Model):
    __tablename__ = "message"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    channel = db.Column(db.String(32), nullable=False, default="pitwall")
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "channel": self.channel,
            "body": self.body,
            "ts": self.created_at.isoformat() if self.created_at else None,
            "deleted": self.deleted,
        }


class Challenge(db.Model):
    __tablename__ = "challenge"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(32))
    points = db.Column(db.Integer, default=100)
    flag_hash = db.Column(db.String(128), nullable=False)
    active = db.Column(db.Boolean, default=True)
    hint = db.Column(db.Text)

    def to_public_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "points": self.points,
            "active": self.active,
            "hint": self.hint,
        }


class Solve(db.Model):
    __tablename__ = "solve"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenge.id"), nullable=False)
    solved_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("username", "challenge_id", name="uniq_user_chal"),)

    challenge = db.relationship("Challenge", backref="solves")


class Announcement(db.Model):
    __tablename__ = "announcement"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {"id": self.id, "body": self.body, "active": self.active}
