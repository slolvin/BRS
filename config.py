
import os

class Config:
    # DB SETTING #
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super secret key'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    FLASKY_MAIL_SUBJECT_PREFIX = '[Flasky]'
    FLASKY_MAIL_SENDER = ''
    FLASKY_ADMIN = os.environ.get('ADMIN')
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    # FILES SETTING #
    SESSION_TYPE = 'filesystem'
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

    # PAGINATION SETTING #
    REWARDS_PER_PAGE = 4
    UPLOAD_FOLDER = 'static/icons/'
    ICONS_FOLDER = 'static/icons/'

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    # MAIL_SERVER =
    # MAIL_PORT =
    # MAIL_USE_TLS =
    # MAIL_USERNAME =
    # MAIL_PASSWORD =
    # SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URL")
    # actually  must be dev_database but for default ese this
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")


class TestingConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}