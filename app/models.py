import hashlib
import re
from datetime import datetime, timedelta

import jwt
from flask import current_app, request
from flask_login import AnonymousUserMixin, UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Role(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(512))

    # Управлять ролями теперь максимально просто: обычная строка
    # Дефолтное значение — 'user'
    role = db.Column(db.String(32), default="user", nullable=False)

    # Ваши старые поля профиля
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())

    # Хелпер-методы для быстрой проверки прав в коде и шаблонах Jinja
    def is_manager(self):
        return self.role in ["manager", "administrator"]

    def is_administrator(self):
        return self.role == "administrator"

    def is_user(self):
        return self.role == "user"


user_favorite_bars = db.Table(
    "user_favorite_bars",
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "bar_id",
        db.Integer,
        db.ForeignKey("bars.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


favorite_drinks = db.Table(
    "favorite_drinks",
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "drink_id",
        db.Integer,
        db.ForeignKey("drinks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class DrunkAction(db.Model):
    """Модель лога выпитых напитков (каждый лог — один факт употребления)"""

    __tablename__ = "drunk_actions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    drink_id = db.Column(
        db.Integer, db.ForeignKey("drinks.id", ondelete="CASCADE"), nullable=False
    )
    timestamp = db.Column(
        db.DateTime, default=datetime.utcnow, index=True
    )  # Дата и время

    # Отношения для быстрого доступа из лога к объектам
    drink = db.relationship("Drink", backref=db.backref("drink_logs", lazy="dynamic"))


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(512))
    email = db.Column(db.String(64), unique=True, index=True)
    role = db.Column(db.String(32), default="user", nullable=False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    # Отношение для избранных напитков
    favorite_drinks = db.relationship(
        "Drink",
        secondary=favorite_drinks,
        lazy="dynamic",
        backref=db.backref("favorited_by", lazy="dynamic"),
    )

    # Новая история выпитого (один ко многим к таблице логов)
    drunk_history = db.relationship(
        "DrunkAction", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    def generate_confirmation_token(self):
        """Генерирует токен для ссылки подтверждения регистрации"""
        s = Serializer(current_app.config["SECRET_KEY"])
        return s.dumps({"confirm": self.id})

    def confirm(self, token):
        """Проверяет токен подтверждения из письма"""
        s = Serializer(current_app.config["SECRET_KEY"])
        try:
            data = s.loads(token, max_age=3600)  # Токен активен 1 час
        except:
            return False
        if data.get("confirm") != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        db.session.commit()
        return True

    def generate_auth_token(self, expiration=604800):
        """
        Генерирует JWT-токен для мобильного приложения.
        по умолчанию срок действия — 7 дней (604800 секунд).
        """
        payload = {
            "user_id": self.id,
            "exp": datetime.utcnow() + timedelta(seconds=expiration),
            "iat": datetime.utcnow(),
        }
        # Шифруем токен с помощью SECRET_KEY вашего Flask-приложения
        return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

    @staticmethod
    def verify_auth_token(token):
        """
        Проверяет токен. Если он валиден — возвращает объект пользователя, иначе None.
        """
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return None  # Срок действия токена истек
        except jwt.InvalidTokenError:
            return None  # Токен подделан или некорректен

        return User.query.get(payload["user_id"])

    def is_manager(self):
        return self.role in ["manager", "administrator"]

    def is_administrator(self):
        return self.role == "administrator"

    def is_user(self):
        return self.role == "user"

    def get_user_name(self):
        return self.name if self.name else self.username

    def is_drink_drunk(self, drink_id):
        """Метод проверки: пил ли пользователь этот напиток вообще хоть раз"""
        return self.drunk_history.filter_by(drink_id=drink_id).first() is not None

    def to_json(self):
        json_user = {
            "username": self.username,
            "member_since": self.member_since,
            "last_seen": self.last_seen,
        }
        return json_user

    favorite_bars = db.relationship(
        "Bar",
        secondary=user_favorite_bars,
        lazy="dynamic",
        backref=db.backref("favorited_by", lazy="dynamic"),
    )

    def log_action(self, action_type, description=None):
        """Метод для быстрой записи действий в журнал"""
        log = ActionLog(
            user_id=self.id, action_type=action_type, description=description
        )
        db.session.add(log)

    def gravatar_hash(self):
        return hashlib.md5(self.email.lower().encode("utf-8")).hexdigest()

    def gravatar_url(self, size=80, default="identicon", rating="g"):
        if request.is_secure:
            url = "https://secure.gravatar.com/avatar"
        else:
            url = "http://www.gravatar.com/avatar"
        hash = hashlib.md5(self.email.strip().lower().encode("utf-8")).hexdigest()
        return f"{url}/{hash}?s={size}&d={default}&r={rating}"

    @property
    def password(self):
        return AttributeError("Password is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def __repr__(self):
        return "<User %r>" % self.username


class Bar(db.Model):
    __tablename__ = "bars"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    admin_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    manager = db.relationship("User", backref="bars", lazy="joined")
    address = db.Column(db.Text())
    city = db.Column(db.Text())
    rate = db.Column(db.Numeric(5, 2))
    drinks = db.relationship(
        "Drink", backref="bar", lazy="joined", cascade="all, delete-orphan"
    )
    qr_secret_hash = db.Column(db.String(128), unique=True, nullable=True)
    latitude = db.Column(db.Float, nullable=True)  # Широта (например: 55.7558)
    longitude = db.Column(db.Float, nullable=True)  # Долгота (например: 37.6173)

    def __repr__(self):
        return f"<Bar {self.name!r}>"

    def get_full_address(self):
        if not self.address:
            return None
        clean_address = re.sub(r"[\s,]+\d+$", "", self.address.strip())
        city_str = f"{self.city.strip()}, " if self.city else "Самара, "
        return f"{city_str}{clean_address}, Россия"

    def get_user_name(self):
        return self.manager.get_user_name() if self.manager else "Неизвестно"

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
            "id": self.id,  # Убедись, что эта строчка ЕСТЬ и ключ называется именно 'id'
            "name": self.name,
            "full_address": self.get_full_address(),
            "rate": float(self.rate) if self.rate else 0.0,
        }

    @staticmethod
    def from_json(json_post):
        # body = json_post.get('body')
        name = json_post.get("name")
        city = json_post.get("city")
        address = json_post.get("address")
        admin_id = json_post.get("admin_id")
        # if body is None or body == '':
        #     raise ValidationError('Bar does not have a body')
        return Bar(name=name, address=address, city=city, admin_id=admin_id)


class Drink(db.Model):
    __tablename__ = "drinks"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    type = db.Column(db.String(64))
    description = db.Column(db.Text())
    score = db.Column(db.Numeric(5, 2))
    image_path = db.Column(db.String(255), nullable=True)
    bar_id = db.Column(
        db.Integer, db.ForeignKey("bars.id", ondelete="CASCADE"), nullable=True
    )

    # НОВОЕ ПОЛЕ: Хранит средний балл (например, 4.50)
    rating = db.Column(db.Numeric(5, 2), default=0.0)
    # Новые поля для геймификации
    volume = db.Column(db.Integer, default=0)  # Объём в мл (например: 500, 250, 50)
    abv = db.Column(
        db.Numeric(4, 1), default=0.0
    )  # Крепость в % (например: 5.0, 12.5, 40.0)

    # НОВАЯ СВЯЗЬ: Позволяет получать все оценки этого напитка через drink.ratings.all()
    ratings = db.relationship(
        "DrinkRating", backref="drink", lazy="dynamic", cascade="all, delete-orphan"
    )

    # МЕТОД ДЛЯ АВТОМАТИЧЕСКОГО ПЕРЕСЧЕТА
    def update_rating(self):
        """Пересчитывает средний рейтинг напитка на основе всех оценок пользователей"""
        all_ratings = self.ratings.all()
        if not all_ratings:
            self.rating = 0.0
        else:
            total = sum(r.value for r in all_ratings)
            self.rating = round(total / len(all_ratings), 2)

    def __repr__(self):
        return f"<Drink {self.name!r}>"

    def to_json(self):
        json_post = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "score": float(self.score) if self.score else None,
            "bar_id": self.bar_id,
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        # body = json_post.get('body')
        name = json_post.get("name")
        drink_type = json_post.get("type")
        description = json_post.get("description")
        bar_id = json_post.get("bar_id")
        # if body is None or body == '':
        #     raise ValidationError('Bar does not have a body')
        return Drink(name=name, type=drink_type, description=description, bar_id=bar_id)


class ActionLog(db.Model):
    __tablename__ = "action_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_type = db.Column(
        db.String(64), nullable=False
    )  # 'register', 'favorite_add', 'rate'
    description = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Связь с пользователем
    user = db.relationship("User", backref=db.backref("actions", lazy="dynamic"))


class DrinkRating(db.Model):
    __tablename__ = "drink_ratings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    drink_id = db.Column(db.Integer, db.ForeignKey("drinks.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # Сама оценка, например от 1 до 5

    # Уникальный индекс, чтобы один пользователь не мог оценить один и тот же напиток дважды
    __table_args__ = (
        db.UniqueConstraint("user_id", "drink_id", name="_user_drink_uc"),
    )


class AnonymousUser(AnonymousUserMixin):
    # Гость не является ни менеджером, ни админом, ни подтвержденным юзером
    def is_manager(self):
        return False

    def is_administrator(self):
        return False

    def is_user(self):
        return False


class BarCheckIn(db.Model):
    __tablename__ = "bar_checkins"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    bar_id = db.Column(db.Integer, db.ForeignKey("bars.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Метод проверки: не истекли ли 3 часа с момента сканирования QR
    def is_expired(self):
        # 2026-й год на дворе, используем чистый тайм-дельта
        return datetime.utcnow() > self.timestamp + timedelta(hours=3)

    def to_json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "bar_id": self.bar_id,
            "timestamp": self.timestamp.isoformat(),
            "is_active": not self.is_expired(),
        }


# Привязываем кастомного гостя к менеджеру логина Flask
login_manager.anonymous_user = AnonymousUser
