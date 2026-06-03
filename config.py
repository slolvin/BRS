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