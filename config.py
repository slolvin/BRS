import os


class Config:
    # DB SETTING #
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super secret key'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    # MAIL SETTING #
    APP_ADMIN = os.environ.get('APP_ADMIN')

    # FILES SETTING #
    SESSION_TYPE = 'filesystem'
    UPLOAD_FOLDER = '/app/static/drinks'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # PAGINATION SETTING #
    DRINKS_PER_PAGE = 3
    ICONS_FOLDER = 'static/icons/'

    # MAIL SERVER #
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'mailpit')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 1025))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'False').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no-reply@brs.app')

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}