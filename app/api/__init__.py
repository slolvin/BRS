from flask import Blueprint, jsonify, request

from ..models import User

api = Blueprint("api", __name__, url_prefix="/api/v1")

from . import authentication, bars, drinks, errors, users


@api.route("/auth/login", methods=["POST"])
def mobile_login():
    """
    Принимает JSON {"email": "...", "password": "..."} от мобильного приложения.
    Возвращает JWT-токен и базовую инфу о пользователе.
    """
    json_data = request.get_json()
    if not json_data:
        return (
            jsonify({"error": "Bad Request", "message": "Отсутствуют JSON данные"}),
            400,
        )

    email = json_data.get("email", "").strip()
    password = json_data.get("password", "")

    # Ищем пользователя в базе данных
    user = User.query.filter_by(email=email).first()

    # Проверяем пароль
    if user is None or not user.verify_password(password):
        return (
            jsonify({"error": "Unauthorized", "message": "Неверный email или пароль"}),
            401,
        )

    # Генерируем токен
    token = user.generate_auth_token()

    return (
        jsonify(
            {
                "status": "success",
                "token": token,  # Тот самый токен, который Swift сохранит у себя
                "user": {"id": user.id, "username": user.username, "role": user.role},
            }
        ),
        200,
    )
