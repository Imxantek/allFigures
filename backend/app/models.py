import enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db=SQLAlchemy()

class Figure(db.Model):
    __tablename__="figure"
    F_ID=db.Column(db.Integer,primary_key=True)
    C_ID=db.Column(db.Integer,db.ForeignKey('character.C_ID'),nullable=False)
    name=db.Column(db.String(100),nullable=False)
    code=db.Column(db.String(100))
    manufacturer=db.Column(db.String(50))
    scale=db.Column(db.String(20))

    offers=db.relationship('Offer',backref='figure',lazy='dynamic')

class StoreEnum(enum.Enum):
    YATTA="yatta.pl"

class StatusEnum(enum.Enum):
    AVAILABLE="available"
    PREORDER="preorder"
    UNAVAILABLE="unavailable"
    ARCHIVAL="archival"

class Offer(db.Model):
    __tablename__="offer"
    O_ID=db.Column(db.Integer,primary_key=True)
    F_ID=db.Column(db.Integer,db.ForeignKey('figure.F_ID'),nullable=False)
    link=db.Column(db.String(500),nullable=False, unique=True)
    store=db.Column(db.Enum(StoreEnum),nullable=False)
    price=db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    status=db.Column(db.Enum(StatusEnum),nullable=False)


class Series(db.Model):
    __tablename__="series"
    S_ID=db.Column(db.Integer,primary_key=True)
    title=db.Column(db.String(100),nullable=False)

    characters=db.relationship('Character',backref='series',lazy='dynamic')

class Character(db.Model):
    __tablename__="character"
    C_ID=db.Column(db.Integer,primary_key=True)
    S_ID=db.Column(db.Integer,db.ForeignKey('series.S_ID'),nullable=False)
    name=db.Column(db.String(100),nullable=False)

    figures=db.relationship('Figure',backref='character',lazy='dynamic')

    __table_args__ = (
        UniqueConstraint('name', 'S_ID', name='unique_character_per_series'),
    )