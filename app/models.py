from werkzeug.security import generate_password_hash,check_password_hash
import hashlib
from datetime import datetime
from flask_login import UserMixin, AnonymousUserMixin
from flask import current_app, request, url_for
from . import db, login_manager
from hashlib import md5


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Permission:
    FOLLOW = 0x01
    COMMENT = 0x02
    WRITE_ARTICLES = 0x04
    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    def add_permission(self, perm):
        if not self.has_permission(perm):
            self.permissions += perm

    def remove_permission(self, perm):
        if self.has_permission(perm):
            self.permissions -= perm

    def reset_permissions(self):
        self.permissions = 0

    def has_permission(self, perm):
        return self.permissions & perm == perm

    def __repr__(self):
        return '<Role %r' % self.name

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.FOLLOW |
                     Permission.COMMENT |
                     Permission.WRITE_ARTICLES, True),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.MODERATE_COMMENTS, False),
            'Administrator': (0xff, False)
        }

        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(256))
    email = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    type = db.Column(db.String(64))
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))

    def gravatar_hash(self):
        return hashlib.md5(self.email.lower().encode('utf-8')).hexdigest()

    def gravatar_url(self, size=80, default='identicon', rating='g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = hashlib.md5(self.email.strip().lower().encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)

        if self.role is None:
            if self.email == current_app.config['APP_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
        if self.role is None:
            self.role = Role.query.filter_by(default=True).first()

        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = self.gravatar_hash()

    @property
    def password(self):
        return AttributeError('Password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can(self, permissions):
        return self.role is not None and \
            (self.role.permissions & permissions) == permissions

    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def __repr__(self):
        return '<User %r>' % self.username

    __mapper_args__ = {
        'polymorphic_identity': 'user',
        'polymorphic_on': 'type'
    }


class Manager(User):
    __tablename__ = 'managers'
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    bars = db.relationship('Bar', backref='manager', lazy=True)

    __mapper_args__ = {
        'polymorphic_identity': 'manager'
    }


class Bar(db.Model):
    __tablename__ = 'bars'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('managers.manager_id'), nullable=False)
    address = db.Column(db.Text())
    city = db.Column(db.Text())
    drinks = db.relationship('Drink', backref='bar', lazy=True)
    rate = db.Column(db.Numeric(5, 2))

    def __repr__(self):
        return '<Bar %r>' % self.name

    def get_user_name(self):
        manager = User.query.get_or_404(self.admin_id)
        return manager.name

    def get_bar_rate(self):
        if len(self.drinks) != 0:
            self.rate = sum(item.score for item in self.drinks)/len(self.drinks)
        else:
            self.rate = 0
        return self.rate


class Drink(db.Model):
    __tablename__ = 'drinks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    type = db.Column(db.String(64))
    description = db.Column(db.Text())
    score = db.Column(db.Numeric(5, 2))
    image = db.Column(db.String(128))
    bar_id = db.Column(db.Integer, db.ForeignKey('bars.id'), nullable=True)

    def __repr__(self):
        return '<Drink %r>' % self.username

class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False


login_manager.anonymous_user = AnonymousUser
