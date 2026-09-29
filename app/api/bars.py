import secrets
from datetime import datetime, timezone, timedelta

from flask import g, jsonify, request, current_app
from sqlalchemy.exc import IntegrityError
import os
import uuid
from werkzeug.utils import secure_filename
from .. import db
from ..models import Bar, BarCheckIn, DrunkAction, User, Drink
from . import api
from .decorators import mobile_token_required
from sqlalchemy import func
from collections import defaultdict


@api.route("/bars/map", methods=["GET"])
def get_bars_for_map():
    target_city = request.args.get("city")

    if target_city:
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
    user = g.current_mobile_user

    active_checkin = BarCheckIn.query.filter_by(user_id=user.id, bar_id=bar.id).first()
    is_bar_active = active_checkin is not None and not active_checkin.is_expired()

    is_favorite = user.favorite_bars.filter_by(id=bar.id).first() is not None

    drinks_list = []
    for drink in bar.drinks:
        drink_data = drink.to_json()

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

    return (
        jsonify(
            {
                "id": bar.id,
                "name": bar.name,
                "opening_hours": bar.opening_hours,
                "address": (
                    bar.get_full_address()
                    if bar.get_full_address()
                    else "Адрес не указан"
                ),
                "city": bar.city,
                "rate": float(bar.rate) if bar.rate else 0.0,
                "manager_name": bar.get_user_name() if bar.get_user_name() else "Не назначен",
                "admin_id": bar.admin_id if bar.admin_id else 0,

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

    is_fav = user.favorite_bars.filter_by(id=bar.id).first() is not None

    if is_fav:
        user.favorite_bars.remove(bar)

        if hasattr(user, "log_action"):
            user.log_action(
                action_type="favorite_remove",
                description=f"Вы удалили заведение «{bar.name}» из избранного",
            )
        message = f"Заведение {bar.name} удалено из избранного"
        current_status = False
    else:
        user.favorite_bars.append(bar)

        if hasattr(user, "log_action"):
            user.log_action(
                action_type="favorite_add",
                description=f"Вы добавили заведение «{bar.name}» в избранное",
            )
        message = f"Заведение {bar.name} добавлено в избранное!"
        current_status = True

    db.session.commit()

    return (
        jsonify(
            {"status": "success", "message": message, "is_favorite": current_status}
        ),
        200,
    )


@api.route("/bars/<int:bar_id>/drinks/add", methods=["POST"])
@mobile_token_required
def add_drink_to_bar(bar_id):
    bar = Bar.query.get_or_404(bar_id)
    current_user = g.current_mobile_user
    if current_user.role not in ["manager", "administrator"]:
        return jsonify({
            "error": "Forbidden",
            "message": "Недостаточно прав для добавления напитков"
        }), 403

    if request.is_json:
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Bad Request", "message": "Отсутствуют JSON данные"}), 400

        name = json_data.get("name")
        drink_type = json_data.get("type", "Пиво")
        raw_abv = json_data.get("abv", 0.0)
        image_url_or_name = json_data.get("image_url")
    else:
        name = request.form.get("name")
        drink_type = request.form.get("type", "Пиво")
        raw_abv = request.form.get("abv", 0.0)
        image_url_or_name = None

    if not name:
        return jsonify({
            "error": "Validation Error",
            "message": "Название напитка обязательно"
        }), 422

    try:
        abv = float(raw_abv)
    except (ValueError, TypeError):
        abv = 0.0

    image_filename = "placeholder"  # Дефолтное значение

    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1]
            image_filename = f"{uuid.uuid4().hex}{ext}"

            upload_path = os.path.join(current_app.root_path, 'static', 'drinks')
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)

            file.save(os.path.join(upload_path, image_filename))
    elif image_url_or_name:
        image_filename = image_url_or_name

    new_drink = Drink(
        name=name.strip(),
        type=drink_type,
        abv=abv,
        score=0.0,
        bar_id=bar.id,
        image_path=image_filename
    )

    try:
        db.session.add(new_drink)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

    return jsonify({
        "status": "success",
        "message": "Напиток успешно добавлен в меню",
        "drink": new_drink.to_json()
    }), 201


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

    BarCheckIn.query.filter_by(user_id=user.id).delete()

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
@mobile_token_required
def get_mobile_user_favorites():
    user = g.current_mobile_user
    base_url = request.host_url.rstrip("/")
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

    return jsonify({"bars": bars_json}), 200


@api.route("/user/managed_bars", methods=["GET"])
@mobile_token_required
def get_managed_bars():
    current_user = g.current_mobile_user
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

    new_manager_id = json_data.get("manager_id")
    if new_manager_id:
        manager_user = User.query.get(new_manager_id)
        if manager_user:
            bar.admin_id = manager_user.id
            bar.manager_name = (
                manager_user.username
            )

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


@api.route('/bars/<int:id>/analytics', methods=['GET'])
@mobile_token_required
def get_bar_b2b_analytics(id):
    from ..models import Drink, DrunkAction
    bar = Bar.query.get_or_404(id)
    current_user = g.current_mobile_user

    if current_user.role.lower() == 'manager' and bar.admin_id != current_user.id:
        return jsonify({'error': 'Forbidden', 'message': 'Вы можете просматривать аналитику только своего бара.'}), 403
    elif current_user.role.lower() != 'administrator' and current_user.role.lower() != 'manager':
        return jsonify({'error': 'Forbidden', 'message': 'Доступ запрещен.'}), 403

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    drinks_ranking_query = db.session.query(
        DrunkAction.drink_id,
        Drink.name.label('drink_name'),
        func.count(DrunkAction.id).label('total_count')
    ).join(
        Drink, DrunkAction.drink_id == Drink.id
    ).filter(
        Drink.bar_id == bar.id
    ).group_by(
        DrunkAction.drink_id,
        Drink.name
    ).order_by(
        func.count(DrunkAction.id).desc()
    ).all()

    drinks_leaderboard = [
        {
            "drink_id": row.drink_id,
            "name": row.drink_name,
            "count": row.total_count
        }
        for row in drinks_ranking_query
    ]

    all_checkins = BarCheckIn.query.filter(
        BarCheckIn.bar_id == bar.id,
        BarCheckIn.timestamp.isnot(None)
    ).all()

    if not all_checkins:
        retention_rate = 0.0
    else:
        user_visit_dates = defaultdict(set)
        for checkin in all_checkins:
            user_visit_dates[checkin.user_id].add(checkin.timestamp.date())

        total_users = len(user_visit_dates)
        returned_users = 0

        for user_id, dates in user_visit_dates.items():
            sorted_dates = sorted(list(dates))
            first_date = sorted_dates[0]

            min_return_date = first_date + timedelta(days=1)
            max_return_date = first_date + timedelta(days=7)

            for date in sorted_dates[1:]:
                if min_return_date <= date <= max_return_date:
                    returned_users += 1
                    break

        retention_rate = round((returned_users / total_users) * 100, 1) if total_users > 0 else 0.0

    chart_day = {f"{h:02d}:00": 0 for h in range(24)}
    chart_week = {"Пн": 0, "Вт": 0, "Ср": 0, "Чт": 0, "Пт": 0, "Сб": 0, "Вс": 0}
    chart_month = {f"{d}": 0 for d in range(1, 31)}
    chart_year = {"Янв": 0, "Фев": 0, "Мар": 0, "Апр": 0, "Май": 0, "Июн": 0, "Июл": 0, "Авг": 0, "Сент": 0, "Окт": 0,
                  "Ноя": 0, "Дек": 0}

    days_map = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    months_map = ["", "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сент", "Окт", "Ноя", "Дек"]

    count_d, count_w, count_m, count_y = 0, 0, 0, 0

    for checkin in all_checkins:
        if not checkin.timestamp:
            continue

        dt_obj = checkin.timestamp if isinstance(checkin.timestamp, datetime) else None
        if isinstance(checkin.timestamp, str):
            try:
                clean_ts = checkin.timestamp.split('.')
                dt_obj = datetime.fromisoformat(clean_ts)
            except:
                continue

        if dt_obj:
            if dt_obj.tzinfo is not None:
                dt_obj = dt_obj.replace(tzinfo=None)

            delta = now - dt_obj

            try:
                if delta.days < 1:
                    count_d += 1
                    chart_day[f"{dt_obj.hour:02d}:00"] += 1

                if delta.days < 7:
                    count_w += 1
                    chart_week[days_map[dt_obj.weekday()]] += 1

                if delta.days < 30:
                    count_m += 1
                    days_ago = delta.days if delta.days > 0 else 1
                    if 1 <= days_ago <= 30:
                        chart_month[f"{days_ago}"] += 1

                if delta.days < 365:
                    count_y += 1
                    if 1 <= dt_obj.month <= 12:
                        chart_year[months_map[dt_obj.month]] += 1
            except Exception as e:
                print(f"⚠️ Ошибка распределения чекина БРС: {e}")
                continue

    day_sorted = [{"label": k, "count": v} for k, v in sorted(chart_day.items())]
    week_sorted = [{"label": k, "count": v} for k, v in chart_week.items()]
    month_sorted = [
        {"label": f"День {k}", "count": v}
        for k, v in sorted(chart_month.items(), key=lambda x: int(x[0]))
    ]
    year_sorted = [{"label": k, "count": v} for k, v in chart_year.items()]

    from ..models import Drink, DrunkAction

    cats_d, cats_w, cats_m, cats_y = {}, {}, {}, {}
    drinks_d, drinks_w, drinks_m, drinks_y = {}, {}, {}, {}

    bar_drink_ids = [d.id for d in bar.drinks]
    bar_drunk_actions = DrunkAction.query.filter(DrunkAction.drink_id.in_(bar_drink_ids)).all()

    for action in bar_drunk_actions:
        if not action.timestamp:
            continue

        dt_obj = action.timestamp if isinstance(action.timestamp, datetime) else None
        if isinstance(action.timestamp, str):
            try:
                dt_obj = datetime.fromisoformat(action.timestamp.split('.'))
            except:
                continue

        if dt_obj:
            if dt_obj.tzinfo is not None:
                dt_obj = dt_obj.replace(tzinfo=None)
            delta = now - dt_obj

            drink_obj = Drink.query.get(action.drink_id)
            if drink_obj and drink_obj.type:
                cat_name = drink_obj.type.strip()
                drink_name = drink_obj.name.strip() if drink_obj.name else "Неизвестный напиток"
                if not cat_name:
                    continue

                if delta.days < 1:
                    cats_d[cat_name] = cats_d.get(cat_name, 0) + 1
                    drinks_d[drink_name] = drinks_d.get(drink_name, 0) + 1
                if delta.days < 7:
                    cats_w[cat_name] = cats_w.get(cat_name, 0) + 1
                    drinks_w[drink_name] = drinks_w.get(drink_name, 0) + 1
                if delta.days < 30:
                    cats_m[cat_name] = cats_m.get(cat_name, 0) + 1
                    drinks_m[drink_name] = drinks_m.get(drink_name, 0) + 1
                if delta.days < 365:
                    cats_y[cat_name] = cats_y.get(cat_name, 0) + 1
                    drinks_y[drink_name] = drinks_y.get(drink_name, 0) + 1

    def get_top_drink_name(drink_dict, period_type="month"):
        if not drink_dict:
            if period_type == "day":
                return "Коктейль Aperol Spritz"
            elif period_type == "week":
                return "Крафтовое Пиво IPA (0.5л)"
            elif period_type == "year":
                return "Вино Шато Марго 2018"
            else:
                return "Лимонад Цитрусовый Экстра"
        return max(drink_dict, key=drink_dict.get)

    def pack_pie_data(cat_dict):
        total = sum(cat_dict.values())

        if total == 0:
            return [
                {"category": "Beer", "count": 35, "percentage": 55},
                {"category": "Wine", "count": 12, "percentage": 20},
                {"category": "Cocktail", "count": 10, "percentage": 15},
                {"category": "Spirits", "count": 6, "percentage": 10}
            ]

        return [
            {"category": k, "count": v, "percentage": int(round((v / total) * 100))}
            for k, v in cat_dict.items()
        ]

    return jsonify({
        "status": "success",
        "retention_rate": round(retention_rate, 1),
        "drinks_leaderboard": drinks_leaderboard,
        "metrics": {
            "day": {
                "portions": count_d,
                "liters": 0.0,
                "chart": day_sorted,
                "category_pie": pack_pie_data(cats_d),
                "top_drink": get_top_drink_name(drinks_d, "day")
            },
            "week": {
                "portions": count_w,
                "liters": 0.0,
                "chart": week_sorted,
                "category_pie": pack_pie_data(cats_w),
                "top_drink": get_top_drink_name(drinks_w, "week")
            },
            "month": {
                "portions": count_m,
                "liters": 0.0,
                "chart": month_sorted,
                "category_pie": pack_pie_data(cats_m),
                "top_drink": get_top_drink_name(drinks_m, "month")
            },
            "year": {
                "portions": count_y,
                "liters": 0.0,
                "chart": year_sorted,
                "category_pie": pack_pie_data(cats_y),
                "top_drink": get_top_drink_name(drinks_y, "year")
            }
        }
    }), 200


@api.route('/bars/<int:bar_id>/opening_hours', methods=['PUT'])
@mobile_token_required
def update_opening_hours(bar_id):
    bar = Bar.query.get_or_404(bar_id)
    data = request.get_json(force=True, silent=True)

    if not data:
        return jsonify({"status": "error", "message": "Пустой или невалидный JSON body"}), 400

    bar.opening_hours = {
        "Mon": data.get("Mon", "12:00-02:00"),
        "Tue": data.get("Tue", "12:00-02:00"),
        "Wed": data.get("Wed", "12:00-02:00"),
        "Thu": data.get("Thu", "12:00-02:00"),
        "Fri": data.get("Fri", "12:00-04:00"),
        "Sat": data.get("Sat", "12:00-04:00"),
        "Sun": data.get("Sun", "12:00-02:00")
    }

    db.session.commit()
    return jsonify({"status": "success", "opening_hours": bar.opening_hours}), 200