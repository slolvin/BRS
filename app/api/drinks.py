from datetime import datetime, timezone, timedelta
from flask import current_app, g, jsonify, request
from sqlalchemy import func
import os
import uuid
import traceback
from werkzeug.utils import secure_filename
from .. import db
from ..models import Bar, BarCheckIn, Drink, DrunkAction
from . import api
from .decorators import mobile_token_required

@api.errorhandler(415)
def handle_415_error(e):
    print("🚨🚨🚨 БРС КРИТИЧЕСКИЙ ДЕБАГ: Поймали ошибку 415! Выводим стек вызовов Python:")
    traceback.print_exc() # Печатает полный путь ошибки в консоль терминала Docker
    return jsonify({"error": "Unsupported Media Type", "message": str(e)}), 415

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


@api.route('/drinks/<int:drink_id>/analytics', methods=['GET'])
@mobile_token_required
def get_drink_b2b_analytics(drink_id):
    drink = Drink.query.get_or_404(drink_id)
    bar = Bar.query.get(drink.bar_id) if drink.bar_id else None
    current_user = g.current_mobile_user

    if current_user.role.lower() == 'manager' and (not bar or bar.admin_id != current_user.id):
        return jsonify({'error': 'Forbidden', 'message': 'Вы можете смотреть аналитику только своих напитков.'}), 403
    elif current_user.role.lower() != 'administrator' and current_user.role.lower() != 'manager':
        return jsonify({'error': 'Forbidden', 'message': 'Доступ запрещен.'}), 403

    all_drink_actions = DrunkAction.query.filter_by(drink_id=drink.id).all()
    drink_vol_liters = (drink.volume if drink.volume else 0) / 1000.0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Словарные сетки под масштабы осей графиков БРС
    chart_day = {f"{h:02d}:00": 0 for h in range(24)}
    chart_week = {"Пн": 0, "Вт": 0, "Ср": 0, "Чт": 0, "Пт": 0, "Сб": 0, "Вс": 0}
    chart_month = {f"{d}": 0 for d in range(1, 31)}
    chart_year = {"Янв": 0, "Фев": 0, "Мар": 0, "Апр": 0, "Май": 0, "Июн": 0, "Июл": 0, "Авг": 0, "Сент": 0, "Окт": 0,
                  "Ноя": 0, "Дек": 0}

    # 🌟 ИСПРАВЛЕНО: Добавлен пустой элемент в начало, чтобы индексы 1-12 совпадали с календарем СУБД
    days_map = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    months_map = ["", "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сент", "Окт", "Ноя", "Дек"]

    portions_d, portions_w, portions_m, portions_y = 0, 0, 0, 0

    for action in all_drink_actions:
        if not action.timestamp:
            continue

        dt_obj = action.timestamp if isinstance(action.timestamp, datetime) else None
        if isinstance(action.timestamp, str):
            try:
                clean_ts = action.timestamp.split('.')
                dt_obj = datetime.fromisoformat(clean_ts[0])
            except:
                continue

        if dt_obj:
            if dt_obj.tzinfo is not None:
                dt_obj = dt_obj.replace(tzinfo=None)

            delta = now - dt_obj

            try:
                # 🟢 СРЕЗ: ДЕНЬ
                if delta.days < 1:
                    portions_d += 1
                    chart_day[f"{dt_obj.hour:02d}:00"] += 1

                # 🔵 СРЕЗ: НЕДЕЛЯ
                if delta.days < 7:
                    portions_w += 1
                    chart_week[days_map[dt_obj.weekday()]] += 1

                # 🟡 СРЕЗ: МЕСЯЦ
                if delta.days < 30:
                    portions_m += 1
                    days_ago = delta.days if delta.days > 0 else 1
                    if 1 <= days_ago <= 30:
                        chart_month[f"{days_ago}"] += 1

                # 🔴 СРЕЗ: ГОД
                if delta.days < 365:
                    portions_y += 1
                    # Безопасное чтение месяца (1-12) из нашего расширенного массива
                    if 1 <= dt_obj.month <= 12:
                        chart_year[months_map[dt_obj.month]] += 1
            except Exception as e:
                print(f"⚠️ Ошибка распределения лога БРС: {e}")
                continue

    # Сортируем списки для JSON под нативные оси Swift Charts
    day_sorted = [{"label": f"{h}", "count": v} for h, v in sorted(chart_day.items())]
    week_sorted = [{"label": k, "count": v} for k, v in chart_week.items()]
    month_sorted = [{"label": f"День {k}", "count": v} for k, v in sorted(chart_month.items(), key=lambda x: int(x[0]))]
    year_sorted = [{"label": k, "count": v} for k, v in chart_year.items()]

    return jsonify({
        "status": "success",
        "metrics": {
            "day": {"portions": portions_d, "liters": round(portions_d * drink_vol_liters, 2), "chart": day_sorted},
            "week": {"portions": portions_w, "liters": round(portions_w * drink_vol_liters, 2), "chart": week_sorted},
            "month": {"portions": portions_m, "liters": round(portions_m * drink_vol_liters, 2), "chart": month_sorted},
            "year": {"portions": portions_y, "liters": round(portions_y * drink_vol_liters, 2), "chart": year_sorted}
        }
    }), 200