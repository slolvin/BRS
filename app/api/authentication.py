import re

from flask import current_app, g, jsonify, request, render_template
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

        # 1. Оставляем текстовую заглушку для старых почтовых клиентов
        msg.body = f"Привет, {username}! Для подтверждения аккаунта перейдите по ссылке: {confirm_url}"

        # 2. 🌟 ДОБАВЛЯЕМ КРАСИВЫЙ HTML-ШАБЛОН (Стиль БРС v4.0)
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Подтверждение регистрации БРС</title>
        </head>
        <body style="margin: 0; padding: 0; background-color: #121215; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">
                <tr>
                    <td align="center" style="padding: 40px 20px;">
                        <!-- Главный контейнер письма -->
                        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 500px; background-color: #1a1a1f; border-radius: 20px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 10px 30px rgba(0,0,0,0.5);">

                            <!-- Шапка с мини-логотипом -->
                            <tr>
                                <td align="center" style="padding: 30px 40px 10px 40px;">
                                    <span style="font-size: 28px; font-weight: 800; color: #ff9500; letter-spacing: 2px;">БРС СИСТЕМА</span>
                                </td>
                            </tr>

                            <!-- Основной контент -->
                            <tr>
                                <td style="padding: 20px 40px 30px 40px; text-align: center;">
                                    <h2 style="margin: 0 0 16px 0; color: #ffffff; font-size: 22px; font-weight: 700;">Привет, {username}! 👋</h2>
                                    <p style="margin: 0 0 24px 0; color: #a1a1aa; font-size: 15px; line-height: 1.6;">
                                        Добро пожаловать в экосистему БРС Самара. Вы успешно зарегистрировали аккаунт. Чтобы активировать его и получить доступ к чекинам и карте заведений, подтвердите ваш email.
                                    </p>

                                    <!-- КНОПКА-ССЫЛКА -->
                                    <table border="0" cellpadding="0" cellspacing="0" style="margin: 30px auto;">
                                        <tr>
                                            <td align="center" style="border-radius: 12px; background-color: #ff9500;">
                                                <a href="{confirm_url}" target="_blank" style="display: inline-block; padding: 14px 36px; font-size: 15px; font-weight: 700; color: #000000; text-decoration: none; border-radius: 12px; transition: background-color 0.2s;">
                                                    Подтвердить аккаунт
                                                </a>
                                            </td>
                                        </tr>
                                    </table>

                                    <!-- Таймер и безопасность -->
                                    <p style="margin: 20px 0 0 0; color: #71717a; font-size: 12px; font-style: italic;">
                                        ⏳ Ссылка активна в течение 1 часа.<br>
                                        Если вы не регистрировались в БРС, просто проигнорируйте это письмо.
                                    </p>
                                </td>
                            </tr>

                            <!-- Подвал -->
                            <tr>
                                <td style="padding: 20px 40px; background-color: rgba(255,255,255,0.02); border-top: 1px solid rgba(255,255,255,0.03); text-align: center;">
                                    <span style="color: #52525b; font-size: 11px;">© 2026 БРС Система. Самара, Россия.</span>
                                </td>
                            </tr>

                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
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
    from itsdangerous import URLSafeTimedSerializer as Serializer

    s = Serializer(current_app.config["SECRET_KEY"])

    # Ссылки на редиректы
    app_deeplink = "http://localhost:8000/auth/login"
    web_login_url = f"{request.host_url.rstrip('/')}/auth/login"

    # Базовые CSS-стили для страниц, чтобы не дублировать код
    base_css = """
    <style>
        body {
            margin: 0; padding: 0;
            background-color: #121215;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex; justify-content: center; align-items: center;
            height: 100vh; color: #ffffff; text-align: center;
        }
        .card {
            background-color: #1a1a1f;
            padding: 40px 30px;
            border-radius: 24px;
            border: 1px solid rgba(255,255,255,0.05);
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            max-width: 400px; width: 90%;
        }
        .icon { font-size: 60px; margin-bottom: 20px; }
        .icon.success { color: #34c759; }
        .icon.info { color: #ff9500; }
        .icon.error { color: #ff3b30; }
        h1 { font-size: 24px; font-weight: 800; margin: 0 0 12px 0; }
        p { color: #a1a1aa; font-size: 15px; line-height: 1.5; margin: 0 0 30px 0; }
        .btn {
            display: inline-block;
            background-color: #ff9500;
            color: #000000;
            text-decoration: none;
            font-weight: 700;
            padding: 14px 32px;
            border-radius: 12px;
            font-size: 15px;
            transition: transform 0.2s, background-color 0.2s;
        }
        .btn:active { transform: scale(0.98); }
        .btn-back {
            display: inline-block;
            background-color: rgba(255,255,255,0.05);
            color: #ffffff;
            text-decoration: none;
            font-weight: 600;
            padding: 12px 28px;
            border-radius: 12px;
            font-size: 14px;
            border: 1px solid rgba(255,255,255,0.1);
        }
    </style>
    """

    try:
        data = s.loads(token, max_age=3600)
        user_id = data.get("confirm")
    except:
        # 1. СТРАНИЦА ОШИБКИ: Токен просрочен или поврежден
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Ошибка Активации БРС</title>
            {base_css}
        </head>
        <body>
            <div class="card">
                <div class="icon error">✕</div>
                <h1>Ссылка недействительна</h1>
                <p>Не удалось активировать аккаунт. Ссылка повреждена, либо её срок действия (1 час) уже истек. Пожалуйста, запросите повторное подтверждение из приложения.</p>
                <a href="{web_login_url}" class="btn-back">На главную сайта</a>
            </div>
        </body>
        </html>
        """, 401

    user = User.query.get_or_404(user_id)

    if user.confirmed:
        # 2. СТРАНИЦА ИНФО: Аккаунт уже активирован ранее
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Аккаунт БРС</title>
            {base_css}
        </head>
        <body>
            <div class="card">
                <div class="icon info">✓</div>
                <h1>Уже подтвержден</h1>
                <p>Ваш аккаунт БРС уже был успешно активирован ранее. Вы можете зайти в мобильное приложение или использовать веб-версию.</p>
                <a href="{app_deeplink}" class="btn">Открыть Приложение</a>
            </div>
        </body>
        </html>
        """, 200

    if user.confirm(token):
        db.session.commit()
        # 3. СТРАНИЦА УСПЕХА: Первая успешная активация аккаунта
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Аккаунт БРС Активирован</title>
            {base_css}
        </head>
        <body>
            <div class="card">
                <div class="icon success">✓</div>
                <h1>Успешная активация!</h1>
                <p>Поздравляем, ваш аккаунт БРС успешно подтвержден. Теперь вам доступны все функции чекинов, интерактивной карты и лидербордов Самары.</p>
                <a href="{app_deeplink}" class="btn">Открыть Приложение</a>
            </div>
        </body>
        </html>
        """, 200
    else:
        # 4. СТРАНИЦА ОШИБКИ: Сбой функции подтверждения
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Ошибка Активации БРС</title>
            {base_css}
        </head>
        <body>
            <div class="card">
                <div class="icon error">✕</div>
                <h1>Ошибка активации</h1>
                <p>Произошел сбой при записи статуса верификации в СУБД. Возможно, токен поврежден.</p>
                <a href="{web_login_url}" class="btn-back">На главную сайта</a>
            </div>
        </body>
        </html>
        """, 400


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

@api.route('/privacy')
def privacy_policy():
    """Умный роут политики конфиденциальности для веба и iOS"""
    user_agent = request.headers.get('User-Agent', '').lower()

    # Проверяем, идет ли запрос от iPhone/Swift-приложения
    is_mobile_app = 'iphone' in user_agent or 'brs' in user_agent or 'cfnetwork' in user_agent

    if is_mobile_app:
        # Отдаем изолированную красивую страницу без лишних меню сайтов
        return render_template('privacy.html')
    else:
        # Для обычного веба отдаем страницу, «завернутую» в вашу общую оболочку
        # Чтобы не создавать два файла, мы можем передать параметр или просто обернуть
        return render_template('privacy_web.html')