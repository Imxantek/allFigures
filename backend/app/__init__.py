import os
from .models import *
from .api import api_bp
from flask import Flask
from dotenv import load_dotenv
def create_app():
    load_dotenv()
    app=Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATION'] = False
    app.config['SQLALCHEMY_ECHO'] = True

    db.init_app(app)
    app.register_blueprint(api_bp)
    return app