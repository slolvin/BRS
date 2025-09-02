from flask import Flask, render_template
from flask_bootstrap import Bootstrap5
# from flask.ext.mail import Mail
# from flask.ext.moment import Moment
from flask_sqlalchemy import SQLAlchemy
from config import config


bootstrap = Bootstrap5()
# mail = Mail()
# moment = Moment()
db = SQLAlchemy()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    bootstrap.init_app(app)
    # mail.init_app(app)
    # moment.init_app(app)
    db.init_app(app)
    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # custom errors and routes

    return app
