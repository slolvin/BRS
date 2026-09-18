import re

from flask import current_app, g, jsonify, request
from flask_httpauth import HTTPBasicAuth
from flask_mail import Message

from .. import db, mail
from ..models import User
from . import api
from .errors import unauthorized

auth = HTTPBasicAuth()


@api.route("/auth/register", methods=["POST"])
def register_mobile_user():
    json_data = request.get_json()
    if not json_data:
        return (
            jsonify({"error": "Bad Request", "message": "Отсутствуют JSON данные"}),
            400,
        )

    username = json_data.get("username", "").strip()
    email = json_data.get("email", "").strip().lower()
    password = json_data.get("password", "")

    # 1. Базовая валидация полей
    if not username or not email or not password:
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "message": "Все поля обязательны для заполнения",
                }
            ),
            422,
        )

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return (
            jsonify({"error": "Validation Error", "message": "Неверный формат email"}),
            422,
        )

    if len(password) < 6:
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "message": "Пароль должен быть не менее 6 символов",
                }
            ),
            422,
        )

    # 2. Проверяем уникальность email и username в СУБД Postgres
    if User.query.filter_by(email=email).first():
        return (
            jsonify(
                {
                    "error": "Conflict",
                    "message": "Пользователь с таким email уже зарегистрирован",
                }
            ),
            409,
        )

    if User.query.filter_by(username=username).first():
        return (
            jsonify({"error": "Conflict", "message": "Имя пользователя уже занято"}),
            409,
        )

    # 3. Создаем нового пользователя с дефолтной ролью 'user'
    new_user = User(
        username=username,
        email=email,
        role="user",
        confirmed=False,  # Ждет подтверждения по почте
    )
    new_user.password = password  # Использует сеттер твоей модели для хэширования

    try:
        db.session.add(new_user)
        db.session.commit()  # СУБД генерирует id

        # 4. ОТПРАВКА ПИСЬМА ЧЕРЕЗ MAILPIT
        token = new_user.generate_confirmation_token()

        # Ссылка, по которой пользователь перейдет для подтверждения (пока ведет на бэк)
        confirm_url = f"{request.host_url.rstrip('/')}/api/v1.0/auth/confirm/{token}"

        msg = Message("Подтверждение регистрации БРС", recipients=[email])
        msg.body = f"Привет, {username}!\n\nДобро пожаловать в БРС. Для подтверждения аккаунта перейдите по ссылке:\n{confirm_url}\n\nСсылка активна 1 час."

        # Отправляем в фоновом режиме (Mailpit перехватит мгновенно)
        mail.send(msg)

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    return (
        jsonify(
            {
                "status": "success",
                "message": "Пользователь успешно создан. Письмо с подтверждением отправлено на почту.",
            }
        ),
        201,
    )


@api.route("/auth/confirm/<token>", methods=["GET"])
def confirm_mobile_user(token):
    """Эндпоинт, на который кликают из письма"""
    # Для MVP мы не знаем ID юзера из GET, поэтому вытаскиваем его из самого JWT токена
    from itsdangerous import URLSafeTimedSerializer as Serializer

    s = Serializer(current_app.config["SECRET_KEY"])
    try:
        data = s.loads(token, max_age=3600)
        user_id = data.get("confirm")
    except:
        return (
            jsonify(
                {
                    "error": "Unauthorized",
                    "message": "Ссылка недействительна или устарела",
                }
            ),
            401,
        )

    user = User.query.get_or_404(user_id)
    if user.confirmed:
        return (
            "<h1>Аккаунт уже был успешно подтвержден! Можете войти в приложение.</h1>",
            200,
        )

    if user.confirm(token):
        return (
            "<h1>Поздравляем! Ваш аккаунт БРС успешно активирован. Откройте мобильное приложение для входа.</h1>",
            200,
        )
    else:
        return "<h1>Ошибка активации. Токен поврежден.</h1>", 400


@auth.verify_password
def verify_password(email_or_token, password):
    if email_or_token == "":
        return False
    if password == "":
        g.current_user = User.verify_auth_token(email_or_token)
        g.token_used = True
        return g.current_user is not None and g.current_user.confirmed

    user = User.query.filter_by(email=email_or_token.lower()).first()
    if not user:
        return False

    g.current_user = user
    g.token_used = False

    if not user.confirmed:
        return False

    return user.verify_password(password)


@api.route("/tokens/", methods=["POST"])
@auth.login_required
def get_token():
    if g.current_user.is_anonymous or g.token_used:
        return unauthorized("Invalid credentials")

    return jsonify(
        {
            "token": g.current_user.generate_auth_token(expiration=3600),
            "expiration": 3600,
        }
    )


@auth.error_handler
def auth_error():
    return unauthorized("Invalid credentials")


# @api.route('/tokens/', methods=['POST'])
# def get_token():
#     if g.current_user.is_anonymous or g.token_used:
#         return unauthorized('Invalid credentials')
#     return jsonify({'token': g.current_user.generate_auth_token(
#         expiration=3600), 'expiration': 3600})


@api.route("/auth/login", methods=["POST"])
def mobile_json_login():
    """Мобильный вход через JSON с точной структурой ответа (status + вложенный user)"""
    json_data = request.get_json()
    if not json_data:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": "Bad Request",
                    "message": "Отсутствуют данные авторизации",
                }
            ),
            400,
        )

    email = json_data.get("email", "").strip().lower()
    password = json_data.get("password", "")

    if not email or not password:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": "Validation Error",
                    "message": "Email и пароль обязательны",
                }
            ),
            422,
        )

    user = User.query.filter_by(email=email).first()

    # 1. Валидация существования юзера и пароля
    if not user or not user.verify_password(password):
        return (
            jsonify(
                {
                    "status": "error",
                    "error": "Unauthorized",
                    "message": "Неверный email или пароль",
                }
            ),
            401,
        )

    # 2. Валидация Mailpit-активации
    if not user.confirmed:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": "Forbidden",
                    "message": "Ваш аккаунт не активирован. Пожалуйста, подтвердите ваш Email по ссылке из письма.",
                }
            ),
            403,
        )

    # Генерируем JWT-токен сессии БРС
    token = user.generate_auth_token(expiration=3600)

    return (
        jsonify(
            {
                "status": "success",
                "token": token,
                "expiration": 3600,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                },
            }
        ),
        200,
    )
