import secrets
from datetime import datetime

from flask import g, jsonify, request
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Bar, BarCheckIn, DrunkAction, User
from . import api
from .decorators import mobile_token_required


@api.route("/bars/map", methods=["GET"])
def get_bars_for_map():
    # Получаем город из параметров запроса iOS (например: ?city=Любляна)
    target_city = request.args.get("city")

    if target_city:
        # Фильтруем бары строго по выбранному в настройках городу
        all_bars = Bar.query.filter_by(city=target_city).all()
    else:
        all_bars = Bar.query.all()

    valid_bars = [
        bar.to_json() for bar in all_bars if bar.get_full_address() is not None
    ]

    return jsonify({"bars": valid_bars}), 200


@api.route("/bars/create", methods=["POST"])
@mobile_token_required
def create_bar():
    current_user = g.current_mobile_user
    if current_user.role != "administrator":
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Доступ запрещен. Создавать бары может только администратор.",
                }
            ),
            403,
        )

    json_data = request.get_json()
    if not json_data:
        return (
            jsonify({"error": "Bad Request", "message": "Отсутствуют JSON данные"}),
            400,
        )

    name = json_data.get("name")
    address = json_data.get("address")
    city = json_data.get("city")

    if not name or not address:
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "message": "Поля name и address обязательны",
                }
            ),
            422,
        )

    admin_id = current_user.id

    generated_qr_secret = secrets.token_hex(32)

    # 3. Создаем экземпляр модели с заполнением qr_secret_hash
    new_bar = Bar(
        name=name.strip(),
        address=address.strip(),
        city=city.strip() if city else "Самара",
        admin_id=admin_id,
        rate=json_data.get("rate", 0.0),
        qr_secret_hash=generated_qr_secret,
    )

    try:
        db.session.add(new_bar)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": "Conflict",
                    "message": f'Бар с именем "{name}" уже существует',
                }
            ),
            409,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    # 4. Возвращаем успешный ответ и прокидываем хэш обратно в iOS приложение
    return (
        jsonify(
            {
                "status": "success",
                "message": "Бар успешно создан",
                "bar": {
                    "id": new_bar.id,
                    "name": new_bar.name,
                    "address": new_bar.get_full_address(),
                    "manager": new_bar.get_user_name(),
                    "qr_secret_hash": new_bar.qr_secret_hash,
                },
            }
        ),
        201,
    )


@api.route("/bars/<int:id>", methods=["GET"])
@mobile_token_required
def get_bar(id):
    bar = Bar.query.get_or_404(id)
    base_url = request.host_url.rstrip("/")
    user = g.current_mobile_user  # Получаем текущего юзера из JWT-токена

    # 1. Проверяем, зачекинен ли юзер
    active_checkin = BarCheckIn.query.filter_by(user_id=user.id, bar_id=bar.id).first()
    is_bar_active = active_checkin is not None and not active_checkin.is_expired()

    is_favorite = user.favorite_bars.filter_by(id=bar.id).first() is not None

    drinks_list = []
    for drink in bar.drinks:
        drink_data = drink.to_json()

        # Проверка DrunkAction для кнопок "Выпить"
        has_drunk = (
            DrunkAction.query.filter_by(user_id=user.id, drink_id=drink.id).first()
            is not None
        )
        drink_data["can_rate"] = is_bar_active and has_drunk

        if drink_data.get("image"):
            drink_data["image_url"] = f"{base_url}/static/drinks/{drink_data['image']}"
        else:
            drink_data["image_url"] = None

        drinks_list.append(drink_data)

    # Отдаем полный JSON для Swift-экрана, включая флаги isCheckedIn и isFavorite
    return (
        jsonify(
            {
                "id": bar.id,
                "name": bar.name,
                "address": (
                    bar.get_full_address()
                    if bar.get_full_address()
                    else "Адрес не указан"
                ),
                "city": bar.city,
                "rate": float(bar.rate) if bar.rate else 0.0,
                "manager_name": bar.get_user_name() if bar.get_user_name() else "Не назначен",
                "admin_id": bar.admin_id if bar.admin_id else 0,

                # 🌟 ИСПРАВЛЕНО: Приводим к snake_case, чтобы JSONDecoder на iOS не паниковал
                "is_checked_in": is_bar_active,
                "is_favorite": is_favorite,
                "drinks": drinks_list,
            }
        ),
        200,
    )


@api.route("/bars/<int:bar_id>/favorite", methods=["POST"])
@mobile_token_required
def toggle_mobile_bar_favorite(bar_id):
    bar = Bar.query.get_or_404(bar_id)
    user = g.current_mobile_user

    # Проверяем наличие бара в избранном по твоей логике СУБД
    is_fav = user.favorite_bars.filter_by(id=bar.id).first() is not None

    if is_fav:
        # Если уже в любимых — удаляем
        user.favorite_bars.remove(bar)

        # Твой кастомный метод логов БРС (если он доступен в модели)
        if hasattr(user, "log_action"):
            user.log_action(
                action_type="favorite_remove",
                description=f"Вы удалили заведение «{bar.name}» из избранного",
            )
        message = f"Заведение {bar.name} удалено из избранного"
        current_status = False
    else:
        # Если еще нет — добавляем
        user.favorite_bars.append(bar)

        if hasattr(user, "log_action"):
            user.log_action(
                action_type="favorite_add",
                description=f"Вы добавили заведение «{bar.name}» в избранное",
            )
        message = f"Заведение {bar.name} добавлено в избранное!"
        current_status = True

    db.session.commit()

    # Возвращаем строгий JSON-статус вместо веб-страницы!
    return (
        jsonify(
            {"status": "success", "message": message, "isFavorite": current_status}
        ),
        200,
    )


@api.route("/bars/<int:bar_id>/drinks/add", methods=["POST"])
@mobile_token_required  # Проверяем Bearer JWT токен менеджера/админа
def add_drink_to_bar(bar_id):
    # 1. Ищем бар, в который добавляем напиток
    bar = Bar.query.get_or_404(bar_id)

    # 2. Проверяем права строковой ролевой модели БРС
    current_user = g.current_mobile_user
    if current_user.role not in ["manager", "administrator"]:
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Недостаточно прав для добавления напитков",
                }
            ),
            403,
        )

    # 3. Валидируем JSON от iOS
    json_data = request.get_json()
    if not json_data:
        return (
            jsonify({"error": "Bad Request", "message": "Отсутствуют JSON данные"}),
            400,
        )

    name = json_data.get("name")
    drink_type = json_data.get("type", "Пиво")
    abv = float(json_data.get("abv", 0.0))

    if not name:
        return (
            jsonify(
                {"error": "Validation Error", "message": "Название напитка обязательно"}
            ),
            422,
        )

    # 4. Создаем напиток с правильным именем колонки СУБД (image_path вместо image)
    from ..models import Drink

    new_drink = Drink(
        name=name.strip(),
        type=drink_type,
        abv=abv,
        score=0.0,  # Защита Swift от null-значений
        bar_id=bar.id,
        image_path=(
            json_data.get("image_url") if json_data.get("image_url") else None
        ),
    )

    try:
        db.session.add(new_drink)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    return (
        jsonify(
            {
                "status": "success",
                "message": "Напиток успешно добавлен в меню",
                "drink": new_drink.to_json(),
            }
        ),
        201,
    )


@api.route("/bars/checkin", methods=["POST"])
@mobile_token_required
def bar_checkin():
    user = g.current_mobile_user
    json_data = request.get_json()

    if not json_data or "qr_hash" not in json_data:
        return (
            jsonify(
                {"error": "Bad Request", "message": "Отсутствует QR-код заведения"}
            ),
            400,
        )

    qr_hash = json_data.get("qr_hash").strip()

    # Ищем бар, которому принадлежит этот QR-код
    bar = Bar.query.filter_by(qr_secret_hash=qr_hash).first()
    if not bar:
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": "Невалидный QR-код. Заведение не найдено.",
                }
            ),
            404,
        )

    # Зачищаем старые протухшие чекины этого юзера, чтобы не копить мусор в СУБД
    BarCheckIn.query.filter_by(user_id=user.id).delete()

    # Создаем новую активную сессию присутствия в баре
    new_checkin = BarCheckIn(
        user_id=user.id, bar_id=bar.id, timestamp=datetime.utcnow()
    )

    try:
        db.session.add(new_checkin)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Вы успешно чекинились в баре {bar.name}! Сессия активна 3 часа.",
                "checkin": new_checkin.to_json(),
            }
        ),
        201,
    )


@api.route("/user/favorites", methods=["GET"])
@mobile_token_required  # Гарантируем проверку Bearer JWT-токена
def get_mobile_user_favorites():
    user = g.current_mobile_user
    base_url = request.host_url.rstrip("/")

    # Запрашиваем Many-to-Many связь, которую мы подтвердили в СУБД
    fav_bars = user.favorite_bars.all()

    bars_json = []
    for bar in fav_bars:
        bars_json.append(
            {
                "id": bar.id,
                "name": bar.name,
                "address": (
                    bar.get_full_address()
                    if bar.get_full_address()
                    else "Адрес не указан"
                ),
                "city": bar.city if bar.city else "Любляна",
                "rate": float(bar.rate) if bar.rate else 0.0,
            }
        )

    # Отдаем строгий JSON с ключом 'bars', который прописан в Swift-модели FavoriteBarsResponse
    return jsonify({"bars": bars_json}), 200


@api.route("/user/managed_bars", methods=["GET"])
@mobile_token_required
def get_managed_bars():
    current_user = g.current_mobile_user

    # Ролевой барьер: отсекаем обычных гостей
    if current_user.role.lower() not in ["manager", "administrator"]:
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Данный раздел доступен только для менеджеров и администраторов БРС.",
                }
            ),
            403,
        )

    if current_user.role.lower() == "administrator":
        bars = Bar.query.all()
    else:
        bars = Bar.query.filter_by(admin_id=current_user.id).all()

    bars_json = []
    for bar in bars:
        bars_json.append(
            {
                "id": bar.id,
                "name": bar.name,
                "address": (
                    bar.get_full_address()
                    if bar.get_full_address()
                    else "Адрес не указан"
                ),
                "city": bar.city,
                "rate": float(bar.rate) if bar.rate else 0.0,
                "qr_secret_hash": (
                    bar.qr_secret_hash
                    if hasattr(bar, "qr_secret_hash")
                    else "no_secret_hash"
                ),
            }
        )

    return jsonify({"status": "success", "bars": bars_json}), 200


@api.route("/bars/<int:bar_id>/edit", methods=["POST"])
@mobile_token_required
def api_edit_bar(bar_id):
    current_user = g.current_mobile_user
    if current_user.role.lower() != "administrator":
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Только суперадмин может менять привязку баров.",
                }
            ),
            403,
        )

    bar = Bar.query.get_or_404(bar_id)
    json_data = request.get_json() or {}

    new_manager_id = json_data.get("manager_id")  # ID юзера, выбранного из списка
    if new_manager_id:
        manager_user = User.query.get(new_manager_id)
        if manager_user:
            bar.admin_id = manager_user.id
            bar.manager_name = (
                manager_user.username
            )  # Синхронизируем имя для техпаспорта СУБД

    bar.name = json_data.get("name", bar.name).strip()
    bar.address = json_data.get("address", bar.address).strip()

    db.session.commit()
    return (
        jsonify(
            {
                "status": "success",
                "message": "Данные бара и управляющий успешно обновлены.",
            }
        ),
        200,
    )
