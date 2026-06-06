from werkzeug.security import generate_password_hash,check_password_hash
import hashlib
from datetime import datetime
from flask_login import UserMixin, AnonymousUserMixin
from flask import current_app, request, url_for
from app.exeptions import ValidationError
from . import db, login_manager
from hashlib import md5
import re
from sqlalchemy.orm import with_polymorphic


@login_manager.user_loader
def load_user(user_id):
    poly_user = with_polymorphic(User, '*')
    return db.session.query(poly_user).filter_by(id=int(user_id)).first()


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
    password_hash = db.Column(db.String(512))
    email = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    type = db.Column(db.String(64))
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))

    def to_json(self):
        json_user = {
            'username': self.username,
            'member_since': self.member_since,
            'last_seen': self.last_seen,
        }
        return json_user

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

        # Проверяем, что это создание нового пользователя, а не загрузка из БД
        if self.id is None:
            if self.role_id is None:
                if self.email == current_app.config.get('APP_ADMIN'):
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
        'polymorphic_on': 'type',
        'with_polymorphic': '*'
    }


class Manager(User):
    __tablename__ = 'managers'
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)

    __mapper_args__ = {
        'polymorphic_identity': 'manager'
    }


class Bar(db.Model):
    __tablename__ = 'bars'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    manager = db.relationship('User', backref='bars', lazy='joined', foreign_keys=[admin_id])
    address = db.Column(db.Text())
    city = db.Column(db.Text())
    rate = db.Column(db.Numeric(5, 2))
    drinks = db.relationship('Drink', backref='bar', lazy='joined', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Bar {self.name!r}>'

    def get_full_address(self):
        if not self.address:
            return None
        clean_address = re.sub(r'[\s,]+\d+$', '', self.address.strip())
        city_str = f"{self.city.strip()}, " if self.city else "Самара, "
        return f"{city_str}{clean_address}, Россия"

    def get_user_name(self):
        # Если связь сработала, берем имя из подгруженного объекта User/Manager
        if self.manager:
            # Убедись, что в User поле называется username (или name, оставь как в твоей модели)
            return getattr(self.manager, 'username', getattr(self.manager, 'name', 'Менеджер'))

        # Резервный ручной запрос, если связь пустая
        user = User.query.get(self.admin_id)
        if user:
            return getattr(user, 'username', getattr(user, 'name', 'Менеджер'))

        return f"Неизвестный менеджер (ID: {self.admin_id})"

    def get_bar_rate(self):
        # 1. Собираем только напитки с выставленной оценкой
        rated_drinks = [item for item in self.drinks if item.score is not None]
        # 2. Если такие напитки есть — безопасно считаем среднее
        if len(rated_drinks) > 0:
            self.rate = sum(item.score for item in rated_drinks) / len(rated_drinks)
        # 3. Если напитков нет или ни у одного нет оценки — рейтинг строго 0
        else:
            self.rate = 0

        return self.rate

    def to_json(self):
        return {
            'id': self.id,  # Убедись, что эта строчка ЕСТЬ и ключ называется именно 'id'
            'name': self.name,
            'full_address': self.get_full_address(),
            'rate': float(self.rate) if self.rate else 0.0
        }

    @staticmethod
    def from_json(json_post):
        # body = json_post.get('body')
        name = json_post.get('name')
        city = json_post.get('city')
        address = json_post.get('address')
        admin_id = json_post.get('admin_id')
        # if body is None or body == '':
        #     raise ValidationError('Bar does not have a body')
        return Bar(name=name, address=address, city=city, admin_id=admin_id)


class Drink(db.Model):
    __tablename__ = 'drinks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    type = db.Column(db.String(64))
    description = db.Column(db.Text())
    score = db.Column(db.Numeric(5, 2))
    image_path = db.Column(db.String(255), nullable=True)
    bar_id = db.Column(db.Integer, db.ForeignKey('bars.id'), nullable=True)

    def __repr__(self):
        return f'<Drink {self.name!r}>'

    def to_json(self):
        json_post = {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'score': float(self.score)  if self.score else None,
            'bar_id': self.bar_id,
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # body = json_post.get('body')
        name = json_post.get('name')
        drink_type = json_post.get('type')
        description = json_post.get('description')
        bar_id = json_post.get('bar_id')
        # if body is None or body == '':
        #     raise ValidationError('Bar does not have a body')
        return Drink(name=name, type=drink_type, description=description, bar_id=bar_id)


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False


login_manager.anonymous_user = AnonymousUser
