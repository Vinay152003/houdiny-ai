from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Lead(db.Model):
    __tablename__ = "leads"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    company     = db.Column(db.String(100), default="")
    role        = db.Column(db.String(100), default="")
    email       = db.Column(db.String(200), default="")
    whatsapp    = db.Column(db.String(50),  default="")   # e.g. +919876543210
    industry    = db.Column(db.String(100), default="")
    notes       = db.Column(db.Text,        default="")
    status           = db.Column(db.String(50), default="New")
    email_status     = db.Column(db.String(50), default="Not Sent")
    whatsapp_status  = db.Column(db.String(50), default="Not Sent")
    created_at       = db.Column(db.DateTime,   default=datetime.utcnow)

    messages = db.relationship(
        "Message", backref="lead", lazy=True,
        cascade="all, delete-orphan"
    )


class Message(db.Model):
    __tablename__ = "messages"
    id         = db.Column(db.Integer, primary_key=True)
    lead_id    = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    channel    = db.Column(db.String(20))   # email / whatsapp
    direction  = db.Column(db.String(10))   # sent / received
    content    = db.Column(db.Text)
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)
