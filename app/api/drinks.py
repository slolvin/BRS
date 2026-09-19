from datetime import datetime

from flask import current_app, g, jsonify, request

from .. import db
from ..models import Bar, BarCheckIn, Drink, DrunkAction
from . import api
from .decorators import mobile_token_required


@api.route("/drinks", methods=["GET"])
@mobile_token_required  # Теперь список напитков защищен токеном
def get_drinks():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("DRINKS_PER_PAGE", 10)

    pagination = Drink.query.paginate(page=page, per_page=per_page, error_out=False)
    drinks = pagination.items
    base_url = request.host_url.rstrip("/")
    user_id = g.current_mobile_user.id

    json_drinks = []
    for drink in drinks:
        drink_data = drink.to_json()

        if drink_data.get("image"):
            drink_data["image_url"] = f"{base_url}/static/drinks/{drink_data['image']}"
        else:
            drink_data["image_url"] = None

        from ..models import DrunkAction

        has_drunk = (
            DrunkAction.query.filter_by(user_id=user_id, drink_id=drink.id).first()
            is not None
        )
        drink_data["can_rate"] = has_drunk

        json_drinks.append(drink_data)

    return (
        jsonify(
            {
                "drinks": json_drinks,
                "current_page": page,
                "per_page": per_page,
                "total_pages": pagination.pages,
                "has_prev": pagination.has_prev,
                "has_next": pagination.has_next,
                "count": pagination.total,
            }
        ),
        200,
    )


@api.route("/drinks/<int:id>", methods=["GET"])
@mobile_token_required  # Карточка напитка под JWT
def get_drink(id):
    drink = Drink.query.get_or_404(id)
    base_url = request.host_url.rstrip("/")
    drink_data = drink.to_json()

    image_name = (
        drink.image_path or drink_data.get("image") or drink_data.get("image_path")
    )
    drink_data["image_url"] = (
        f"{base_url}/static/drinks/{image_name}" if image_name else None
    )

    # Очищаем лишние поля
    drink_data.pop("image_path", None)
    drink_data.pop("image", None)

    # Добавляем для iOS флаг проверки: заказывал ли пользователь этот напиток ранее
    # и оценивал ли уже (чтобы iOS сразу блокировала кнопки звезд, если нельзя оценивать)
    has_drunk = (
        DrunkAction.query.filter_by(
            user_id=g.current_mobile_user.id, drink_id=id
        ).first()
        is not None
    )

    # Предполагаем, что мы добавили отметку об оценке в DrunkAction (например, поле rated=True)
    # Если поля rated нет, мы можем временно проверять просто факт наличия заказа
    drink_data["can_rate"] = has_drunk

    return jsonify(drink_data), 200


@api.route("/drinks/<int:id>/rate", methods=["POST"])
@mobile_token_required  # Оценивать могут только верифицированные пользователи по JWT
def rate_drink(id):
    drink = Drink.query.get_or_404(id)
    user = g.current_mobile_user

    from ..models import BarCheckIn

    active_checkin = BarCheckIn.query.filter_by(
        user_id=user.id, bar_id=drink.bar_id
    ).first()
    if not active_checkin or active_checkin.is_expired():
        if active_checkin:
            db.session.delete(active_checkin)
            db.session.commit()

        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Для оценки напитка необходимо отсканировать QR-код на столе этого заведения.",
                }
            ),
            403,
        )

    # 1. ЗАЩИТА ОТ НАКРУТКИ: Проверяем, пил ли пользователь этот напиток вообще
    # Ищем последнюю запись употребления, которую юзер еще НЕ оценивал
    action = (
        DrunkAction.query.filter_by(user_id=user.id, drink_id=id)
        .order_by(DrunkAction.timestamp.desc())
        .first()
    )

    if not action:
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": 'Вы не можете оценить напиток, пока не отметите факт его употребления (нажав "Выпить").',
                }
            ),
            403,
        )

    # Если в модели DrunkAction есть флаг rated (был ли этот бокал уже оценен)
    if hasattr(action, "is_rated") and action.is_rated:
        return (
            jsonify(
                {
                    "error": "Conflict",
                    "message": "Вы уже оценили этот бокал. Чтобы оценить снова, добавьте новую запись употребления.",
                }
            ),
            409,
        )

    # 2. Получаем оценку из Swift
    json_data = request.get_json()
    if not json_data or "rating" not in json_data:
        return (
            jsonify({"error": "Bad Request", "message": "Отсутствует поле rating"}),
            400,
        )

    try:
        new_rating = int(json_data["rating"])
        if new_rating < 1 or new_rating > 5:
            return (
                jsonify(
                    {
                        "error": "Validation Error",
                        "message": "Оценка должна быть от 1 до 5",
                    }
                ),
                422,
            )
    except ValueError:
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "message": "Оценка должна быть целым числом",
                }
            ),
            422,
        )

    try:
        # 3. Алгоритм экспоненциального сглаживания (из твоей логики бэкенда)
        if not drink.score or float(drink.score) == 0.0:
            drink.score = float(new_rating)
        else:
            current_score = float(drink.score)
            weight = 0.2
            updated_score = (current_score * (1 - weight)) + (new_rating * weight)
            drink.score = round(updated_score, 2)

        # 4. Помечаем эту конкретную запись употребления как "оцененную"
        if hasattr(action, "is_rated"):
            action.is_rated = True

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    # 5. Возвращаем новый score в iOS для мгновенного обновления звездочек
    return (
        jsonify(
            {
                "status": "success",
                "message": "Оценка учтена",
                "new_score": float(drink.score),
            }
        ),
        200,
    )


@api.route("/drinks/<int:id>/drink", methods=["POST"])
@mobile_token_required  # Требуем Bearer JWT токен юзера
def log_drink_action(id):
    drink = Drink.query.get_or_404(id)
    user = g.current_mobile_user

    # 1. ЗАЩИТА БРС: Проверяем, зачекинен ли пользователь в баре, где налит напиток
    active_checkin = BarCheckIn.query.filter_by(
        user_id=user.id, bar_id=drink.bar_id
    ).first()
    if not active_checkin or active_checkin.is_expired():
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Вы не можете отметить напиток выпитым, пока не выполните QR-чекин в этом заведении.",
                }
            ),
            403,
        )

    # 2. Создаем экземпляр транзакции (один бокал = одна запись в таблице)
    new_action = DrunkAction(
        user_id=user.id,
        drink_id=drink.id,
        timestamp=datetime.utcnow(),  # Фиксируем точное время по UTC
    )

    try:
        db.session.add(new_action)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Запись добавлена: выпит 1 бокал {drink.name}.",
                "action_id": new_action.id,
            }
        ),
        201,
    )


@api.route("/bars/<int:bar_id>/drinks/add", methods=["POST"])
@mobile_token_required  # Из паспорта: верифицирует токен и пишет юзера в g.current_mobile_user
def api_add_drink(bar_id):
    """
    Унифицированный мобильный эндпоинт добавления напитка менеджером/администратором.
    Заменяет старую ручку, корректно работает со структурой СУБД (image_path, score).
    """
    current_user = g.current_mobile_user
    bar = Bar.query.get_or_404(bar_id)

    if current_user.role.lower() == "manager":
        # Проверяем, привязан ли этот бар к текущему менеджеру в Postgres (по полю admin_id)
        if bar.admin_id != current_user.id:
            return (
                jsonify(
                    {
                        "error": "Forbidden",
                        "message": "Доступ запрещен. Вы можете управлять меню только своего заведения.",
                    }
                ),
                403,
            )

    # Если это не менеджер и не админ сети — полный отказ
    elif current_user.role.lower() != "administrator":
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "Недостаточно прав для выполнения этого действия.",
                }
            ),
            403,
        )

    # 3. Валидируем JSON от iOS-формы
    json_data = request.get_json()
    if not json_data:
        return (
            jsonify({"error": "Bad Request", "message": "Отсутствуют JSON данные"}),
            400,
        )

    name = json_data.get("name")
    drink_type = json_data.get("type", "Пиво")
    description = json_data.get("description", "")

    if not name:
        return (
            jsonify(
                {"error": "Validation Error", "message": "Название напитка обязательно"}
            ),
            422,
        )

    # Безопасный сбор объема и крепости под типы СУБД
    try:
        volume = int(json_data.get("volume", 0))
    except (ValueError, TypeError):
        volume = 0

    try:
        abv = float(json_data.get("abv", 0.0))
    except (ValueError, TypeError):
        abv = 0.0

    # 4. Создаем напиток со всеми обязательными системными полями базы БРС
    new_drink = Drink(
        name=name.strip(),
        type=drink_type.strip(),
        description=description.strip(),
        volume=volume,
        abv=abv,
        score=0.0,  # Гарантированная защита Swift от падения на null-значениях
        bar_id=bar.id,
        # Используем честное имя колонки из вашей рабочей СУБД!
        image_path=json_data.get("image_url") if json_data.get("image_url") else None,
    )

    # 5. Сохраняем трансляцию в базу
    try:
        db.session.add(new_drink)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"❌ Ошибка сохранения напитка в Postgres: {e!s}")
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    # 6. Успешный ответ 201 с JSON-представлением объекта под iOS-модель
    return (
        jsonify(
            {
                "status": "success",
                "message": "Напиток успешно добавлен в меню заведения",
                "drink": {
                    "id": new_drink.id,
                    "name": new_drink.name,
                    "type": new_drink.type,
                    "volume": new_drink.volume,
                    "abv": new_drink.abv,
                    "score": new_drink.score,
                },
            }
        ),
        201,
    )


@api.route('/drinks/<int:drink_id>/edit', methods=['POST'])
@mobile_token_required
def api_edit_drink(drink_id):
    """
    Обновляет данные напитка (имя, тип, описание, объем, градус).
    Доступно суперадмину или менеджеру этого конкретного заведения.
    """
    drink = Drink.query.get_or_404(drink_id)
    bar = Bar.query.get(drink.bar_id) if drink.bar_id else None
    current_user = g.current_mobile_user

    # Жесткий барьер безопасности: проверяем права на этот бар в СУБД
    if current_user.role.lower() == 'manager':
        if not bar or bar.admin_id != current_user.id:
            return jsonify(
                {'error': 'Forbidden', 'message': 'Вы можете редактировать напитки только своего бара.'}), 403
    elif current_user.role.lower() != 'administrator':
        return jsonify({'error': 'Forbidden', 'message': 'Доступ запрещен.'}), 403

    json_data = request.get_json() or {}

    # Считываем измененные данные из JSON
    drink.name = json_data.get('name', drink.name).strip()
    drink.type = json_data.get('type', drink.type).strip()
    drink.description = json_data.get('description', drink.description).strip()

    try:
        drink.volume = int(json_data.get('volume', drink.volume))
        drink.abv = float(json_data.get('abv', drink.abv))
    except (ValueError, TypeError):
        return jsonify(
            {'error': 'Validation Error', 'message': 'Неверный формат числовых данных объема или градуса.'}), 422

    # Каноничный лог действия в СУБД для Менеджера
    if hasattr(current_user, 'log_action'):
        current_user.log_action(
            action_type='edit_drink',
            description=f'Обновлен напиток: {drink.name} (Бар: {bar.name if bar else "Глобальный"})'
        )

    db.session.commit()
    return jsonify({
        'status': 'success',
        'message': f'Напиток "{drink.name}" успешно обновлен.',
        'drink': {'id': drink.id, 'name': drink.name, 'volume': drink.volume, 'abv': drink.abv}
    }), 200


@api.route('/drinks/<int:drink_id>/delete', methods=['POST'])
@mobile_token_required
def api_delete_drink(drink_id):
    """
    Полностью удаляет напиток из меню заведения в СУБД Postgres.
    Доступно суперадмину или менеджеру этого конкретного заведения.
    """
    drink = Drink.query.get_or_404(drink_id)
    bar = Bar.query.get(drink.bar_id) if drink.bar_id else None
    current_user = g.current_mobile_user

    # Жесткий барьер безопасности БРС
    if current_user.role.lower() == 'manager':
        if not bar or bar.admin_id != current_user.id:
            return jsonify({'error': 'Forbidden', 'message': 'Вы можете удалять напитки только своего бара.'}), 403
    elif current_user.role.lower() != 'administrator':
        return jsonify({'error': 'Forbidden', 'message': 'Доступ запрещен.'}), 403

    # Системный лог действия в Postgres перед стиранием
    if hasattr(current_user, 'log_action'):
        current_user.log_action(
            action_type='delete_drink',
            description=f'Удален напиток: {drink.name} (Бар: {bar.name if bar else "Глобальный"})'
        )

    db.session.delete(drink)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Напиток успешно удален из базы данных БРС.'
    }), 200