
from flask import g, jsonify, request
from flask_login import current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from .. import db
from ..models import ActionLog, Drink, DrunkAction, User
from . import api

# from .decorators import login_required
from .decorators import mobile_token_required


@api.route("/user/profile")
@mobile_token_required
def get_user_profile():
    # В продакшене: user = g.current_user
    user = g.current_mobile_user

    result = (
        db.session.query(
            func.count(DrunkAction.id).label("glasses_count"),
            func.sum(Drink.volume).label("total_ml"),
            func.avg(Drink.abv).label("average_abv"),
        )
        .join(Drink, DrunkAction.drink_id == Drink.id)
        .filter(DrunkAction.user_id == user.id)
        .first()
    )

    count_glasses = result.glasses_count or 0
    total_ml = result.total_ml or 0
    # Принудительно приводим к float, чтобы в JSON улетело дробное число (Double для Swift)
    avg_abv = float(result.average_abv) if result.average_abv else 0.0
    total_liters = float(total_ml / 1000.0)

    # === РАСЧЕТ ЛЮБИМОГО НАПИТКА ===
    fav_drink_query = (
        db.session.query(Drink, func.count(DrunkAction.id).label("drink_count"))
        .join(DrunkAction, DrunkAction.drink_id == Drink.id)
        .filter(DrunkAction.user_id == user.id)
        .group_by(Drink.id)
        .order_by(func.count(DrunkAction.id).desc())
        .first()
    )

    # Берем имя любимого напитка
    fav_drink_name = (
        fav_drink_query[0].name
        if fav_drink_query and fav_drink_query[0]
        else "Не определен"
    )

    # Расчет звания месяца
    if total_liters == 0:
        monthly_badge = "Трезвенник"
    elif total_liters >= 5.0 and avg_abv <= 6.0:
        monthly_badge = "ПИВО"
    elif avg_abv >= 30.0 and total_liters >= 1.0:
        monthly_badge = "Пират"
    else:
        monthly_badge = "Эстет"

    # Форматируем дату регистрации
    reg_date = (
        user.member_since.strftime("%Y-%m-%d")
        if hasattr(user, "member_since") and user.member_since
        else "2026-05-28"
    )

    # Собираем логи действий (ActionLog)
    user_logs = user.actions.order_by(ActionLog.timestamp.desc()).limit(10).all()
    logs_data = []
    for log in user_logs:
        logs_data.append(
            {
                "action_type": log.action_type,
                "description": log.description,
                "timestamp": (
                    log.timestamp.strftime("%Y-%m-%d %H:%M") if log.timestamp else ""
                ),
            }
        )

    # Собираем историю выпитого (DrunkAction)
    drunk_actions = (
        user.drunk_history.order_by(DrunkAction.timestamp.desc()).limit(15).all()
    )
    drunk_data = []
    for action in drunk_actions:
        if action.drink:
            drunk_data.append(
                {
                    "id": action.id,
                    "drink_name": action.drink.name,
                    "type": action.drink.type,
                    "volume": action.drink.volume or 0,
                    "abv": float(action.drink.abv) if action.drink.abv else 0.0,
                    "timestamp": (
                        action.timestamp.strftime("%d.%m %H:%M")
                        if action.timestamp
                        else ""
                    ),
                }
            )

    # =========================================================================
    # ВАЖНО: СТРОГО СОБЛЮДАЕМ СТРУКТУРУ КЛЮЧЕЙ PROFILESTATS ДЛЯ SWIFT
    # =========================================================================
    stats_payload = {
        "total_glasses": int(count_glasses),
        "total_liters": float(round(total_liters, 2)),
        "avg_abv": float(round(avg_abv, 1)),
        "favorite_drink": str(fav_drink_name),
        "registered_at": str(reg_date),
    }

    # === СОБИРАЕМ СПИСОК ИЗБРАННОГО (Многие-ко-многим из Postgres) ===
    favorite_drinks_list = []
    # user.favorite_drinks.all() вытащит все напитки, добавленные по звездочке
    if hasattr(user, 'favorite_drinks') and user.favorite_drinks:
        for drink in user.favorite_drinks.all():
            favorite_drinks_list.append(drink.to_json())

    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "email": getattr(user, "email", "user@brs.com"),
            "role": user.role if user.role else "user",
            "monthly_badge": monthly_badge,
            "stats": stats_payload,
            "recent_logs": logs_data,
            "drunk_history": drunk_data,

            # 🌟 ДОБАВЛЯЕМ НОВЫЙ МАССИВ ДЛЯ ИЗБРАННЫХ НАПИТКОВ
            "favorite_drinks": favorite_drinks_list
        }
    )


@api.route("/user/favorite-bars", methods=["GET"])
def get_user_favorite_bars():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.get(3) or User.query.first()

    if not user:
        return jsonify({"bars": []}), 200

    fav_bars = user.favorite_bars.all()

    bars_json = []
    for bar in fav_bars:
        bars_json.append(
            {
                "id": bar.id,
                "name": bar.name,
                "address": bar.address or "Адрес не указан",
                "city": bar.city or "Самара",
                "rate": float(bar.rate) if bar.rate else 0.0,
            }
        )

    return jsonify({"bars": bars_json}), 200


@api.route("/user/update-location", methods=["POST"])
def update_user_location():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.get(3) or User.query.first()

    if not user:
        return jsonify({"error": "Not Found", "message": "Пользователь не найден"}), 404

    json_data = request.get_json()
    if not json_data or "city" not in json_data:
        return jsonify({"error": "Bad Request", "message": "Город не указан"}), 400

    user.location = json_data.get("city").strip()
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Город успешно изменен на {user.location}",
                "current_city": user.location,
            }
        ),
        200,
    )


@api.route("/admin/users", methods=["GET"])
@mobile_token_required
def api_users_management():
    """Возвращает отфильтрованный список всех пользователей для админки iOS."""
    current_user = g.current_mobile_user

    # Жесткий барьер безопасности верховного админа
    if current_user.role.lower() != "administrator":
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Доступ запрещен. Только для администраторов.",
                }
            ),
            403,
        )

    # Поддерживаем ваш веб-поиск ?search=...
    search_query = request.args.get("search", "").strip()
    query = User.query

    if search_query:
        query = query.filter(User.username.ilike(f"%{search_query}%"))

    all_users = query.order_by(User.username.asc()).all()

    # Формируем JSON с полями под спецификацию iOS
    users_list = []
    for user in all_users:
        users_list.append(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "name": user.name or "",
                "location": user.location or "",
                "about_me": user.about_me or "",
                "confirmed": user.confirmed,
            }
        )

    return jsonify({"status": "success", "users": users_list}), 200


@api.route("/admin/users/<int:user_id>/edit", methods=["POST"])
@mobile_token_required
def api_edit_profile_admin(user_id):
    """Принимает плоский JSON и обновляет профиль любого пользователя."""
    current_user = g.current_mobile_user

    if current_user.role.lower() != "administrator":
        return jsonify({"error": "Forbidden", "message": "Доступ запрещен."}), 403

    target_user = User.query.get_or_404(user_id)
    json_data = request.get_json() or {}

    # Заменяем веб-логику form.validate_on_submit() на проверку JSON данных
    new_username = json_data.get("username", "").strip()
    new_email = json_data.get("email", "").strip()
    new_role = (
        json_data.get("role", "").lower().strip()
    )  # 'user', 'manager', 'administrator'

    if not new_username or not new_email or not new_role:
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "message": "Поля username, email и role обязательны.",
                }
            ),
            422,
        )

    # Проверка на дубликаты (уникальность в СУБД)
    if (
        new_username != target_user.username
        and User.query.filter_by(username=new_username).first()
    ):
        return jsonify({"error": "Conflict", "message": "Этот никнейм уже занят."}), 409
    if new_email != target_user.email and User.query.filter_by(email=new_email).first():
        return (
            jsonify(
                {"error": "Conflict", "message": "Этот Email уже зарегистрирован."}
            ),
            409,
        )

    # Сохраняем изменения в модель СУБД из JSON
    target_user.username = new_username
    target_user.email = new_email
    target_user.role = new_role
    target_user.name = json_data.get("name", "").strip()
    target_user.location = json_data.get("location", "").strip()
    target_user.about_me = json_data.get("about_me", "").strip()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Профиль пользователя @{target_user.username} успешно обновлен.",
                "user": {
                    "id": target_user.id,
                    "username": target_user.username,
                    "role": target_user.role,
                },
            }
        ),
        200,
    )


@api.route("/admin/managers", methods=["GET"])
@mobile_token_required
def get_all_managers():
    """Возвращает список всех пользователей с ролью manager или administrator для назначения в бары."""
    current_user = g.current_mobile_user
    if current_user.role.lower() != "administrator":
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Доступ разрешен только администраторам.",
                }
            ),
            403,
        )

    # Вытаскиваем из СУБД тех, кто имеет право управлять заведениями
    managers = (
        User.query.filter(User.role.in_(["manager", "administrator"]))
        .order_by(User.username.asc())
        .all()
    )

    return (
        jsonify(
            {
                "status": "success",
                "managers": [{"id": m.id, "username": m.username} for m in managers],
            }
        ),
        200,
    )


@api.route("/user/edit_profile", methods=["POST"])
@mobile_token_required
def api_edit_profile():
    """
    Мобильный эндпоинт редактирования профиля текущим пользователем.
    Принимает плоский JSON, поддерживает опциональную смену пароля.
    """
    current_user = g.current_mobile_user
    json_data = request.get_json() or {}

    new_email = json_data.get("email", "").strip()
    new_name = json_data.get("name", "").strip()
    new_location = json_data.get("location", "").strip()
    new_about_me = json_data.get("about_me", "").strip()

    # Блок безопасности (смена пароля)
    password = json_data.get("password", "")
    password_confirm = json_data.get("password_confirm", "")

    if not new_email:
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "message": "Email обязателен для заполнения",
                }
            ),
            422,
        )

    # 1. Проверка уникальности Email, если пользователь решил его поменять
    if new_email != current_user.email:
        email_exists = User.query.filter_by(email=new_email).first()
        if email_exists:
            return (
                jsonify(
                    {
                        "error": "Conflict",
                        "message": "Этот Email уже занят другим аккаунтом",
                    }
                ),
                409,
            )
        current_user.email = new_email

    # 2. Обновляем личные данные в Postgres
    current_user.name = new_name
    current_user.location = new_location
    current_user.about_me = new_about_me

    # 3. Валидация и хэширование нового пароля из блока «Безопасность»
    if password or password_confirm:
        if password != password_confirm:
            return (
                jsonify(
                    {
                        "error": "Validation Error",
                        "message": "Введенные пароли не совпадают",
                    }
                ),
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

        # Записываем в базу безопасный хэш вместо сырой строки!
        current_user.password_hash = generate_password_hash(password)

    # 4. Пишем каноничный системный лог БРС, как в вашей веб-версии
    if hasattr(current_user, "log_action"):
        current_user.log_action(
            action_type="edit_profile",
            description="Вы обновили данные своего профиля через мобильное приложение",
        )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    return (
        jsonify(
            {
                "status": "success",
                "message": "Профиль успешно обновлен в СУБД БРС",
                "user": {
                    "id": current_user.id,
                    "username": current_user.username,
                    "email": current_user.email,
                },
            }
        ),
        200,
    )
