import base64
import io
import os
import random
import secrets
from datetime import datetime, timedelta

import qrcode
from flask import (abort, flash, redirect, render_template, request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from config import Config

from .. import db
from ..decorators import admin_required
from ..models import ActionLog, Bar, Drink, DrinkRating, DrunkAction, User
from . import main
from .forms import EditProfileAdminForm


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )

@main.route('/privacy')
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


@main.route("/user/<username>")
@login_required
def user(username):
    this_user = User.query.filter_by(username=username).first_or_404()

    user_logs = (
        db.session.query(ActionLog)
        .filter(ActionLog.user_id == this_user.id)
        .options(joinedload(ActionLog.user))
        .order_by(ActionLog.timestamp.desc())
        .limit(10)
        .all()
    )

    drunk_history_optimized = (
        this_user.drunk_history.options(joinedload(DrunkAction.drink))
        .order_by(DrunkAction.timestamp.desc())
        .limit(15)
        .all()
    )

    favorite_bars = this_user.favorite_bars.all()
    managed_bars = []
    if this_user.role in ["manager", "administrator"]:
        if this_user.role == "administrator":
            managed_bars = Bar.query.order_by(Bar.name.asc()).all()
        else:
            managed_bars = (
                Bar.query.filter_by(admin_id=this_user.id)
                .order_by(Bar.name.asc())
                .all()
            )

    managed_bars_with_qr = []
    for b in managed_bars:
        b_qr = None
        if b.qr_secret_hash:
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(b.qr_secret_hash)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b_qr = base64.b64encode(buf.getvalue()).decode("utf-8")
        managed_bars_with_qr.append({"bar": b, "qr_base64": b_qr})

    now = datetime.utcnow()
    periods = {
        "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
        "year": now - timedelta(days=365),
        "all_time": datetime.min,
    }

    stats = {}
    for period_name, start_date in periods.items():
        result = (
            db.session.query(
                func.count(DrunkAction.id).label("glasses_count"),
                func.sum(Drink.volume).label("total_ml"),
                func.avg(Drink.abv).label("average_abv"),
            )
            .join(Drink, DrunkAction.drink_id == Drink.id)
            .filter(
                DrunkAction.user_id == this_user.id, DrunkAction.timestamp >= start_date
            )
            .first()
        )

        count_glasses = result.glasses_count or 0
        total_ml = result.total_ml or 0
        avg_abv = float(result.average_abv) if result.average_abv else 0.0

        stats[period_name] = {
            "count": count_glasses,
            "volume": round(total_ml / 1000.0, 2),
            "abv": round(avg_abv, 1),
        }

    fav_drink_query = (
        db.session.query(Drink, func.count(DrunkAction.id).label("drink_count"))
        .join(DrunkAction, DrunkAction.drink_id == Drink.id)
        .filter(DrunkAction.user_id == this_user.id)
        .group_by(Drink.id)
        .order_by(func.count(DrunkAction.id).desc())
        .first()
    )

    fav_drink = fav_drink_query[0] if fav_drink_query else None

    month_volume = stats["month"]["volume"]
    month_abv = stats["month"]["abv"]

    if month_volume == 0:
        monthly_badge, badge_color = "Трезвенник", "secondary"
        badge_desc = "В этом месяце вы не отметили ни одного бокала."
    elif month_volume >= 5.0 and month_abv <= 6.0:
        monthly_badge, badge_color = "ПИВО", "warning"
        badge_desc = "Упор на объём и классический солод. Легенда пабов!"
    elif month_abv >= 30.0 and month_volume >= 1.0:
        monthly_badge, badge_color = "Пират", "danger"
        badge_desc = "Предпочитаете чистый крепкий алкоголь. Йо-хо-хо!"
    else:
        monthly_badge, badge_color = "Коктейльный Эстет", "primary"
        badge_desc = "Умеренное потребление и разнообразие вкусов."

    return render_template(
        "user.html",
        user=this_user,
        user_logs=user_logs,
        favorite_bars=favorite_bars,
        stats=stats,
        drunk_history_optimized=drunk_history_optimized,
        fav_drink=fav_drink,
        monthly_badge=monthly_badge,
        badge_desc=badge_desc,
        badge_color=badge_color,
        managed_bars=managed_bars_with_qr,
    )


@main.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    user_logs = (
        current_user.actions.order_by(ActionLog.timestamp.desc()).limit(10).all()
    )
    favorite_bars = current_user.favorite_bars.all()

    if request.method == "POST":
        current_user.name = request.form["name"]
        current_user.location = request.form["location"]
        current_user.email = request.form["email"]

        current_user.log_action(
            action_type="edit_profile", description="Вы обновили данные своего профиля"
        )

        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash("Your profile has been updated.")
        return redirect(url_for(".user", username=current_user.username))

    return render_template(
        "edit_profile.html",
        user=current_user,
        user_logs=user_logs,
        favorite_bars=favorite_bars,
    )


@main.route("/edit-profile/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)

    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.role = form.role.data
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        # user.confirmed = form.confirmed.data (если используете флаг подтверждения)

        selected_bar_id = form.assigned_bar.data

        old_bars = Bar.query.filter_by(admin_id=user.id).all()
        for b in old_bars:
            b.admin_id = None
            b.manager_name = "Не назначен"

        if user.role in ["manager", "administrator"] and selected_bar_id > 0:
            target_bar = Bar.query.get(selected_bar_id)
            if target_bar:
                target_bar.admin_id = user.id
                target_bar.manager_name = (
                    user.username
                )

        db.session.commit()
        flash(f"Профиль пользователя @{user.username} успешно обновлен.", "success")
        return redirect(url_for(".user", username=user.username))

    form.email.data = user.email
    form.username.data = user.username
    form.role.data = user.role
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me

    current_bar = Bar.query.filter_by(admin_id=user.id).first()
    form.assigned_bar.data = current_bar.id if current_bar else 0

    return render_template("edit_profile_admin.html", form=form, user=user)


@main.route("/")
def index():
    return redirect(url_for(".get_bars_list"))


@main.route("/users-management/")
@login_required
@admin_required
def users_management():
    search_query = request.args.get("search", "").strip()

    query = User.query

    if search_query:
        query = query.filter(User.username.ilike(f"%{search_query}%"))

    all_users = query.order_by(User.username.asc()).all()

    return render_template(
        "users_management.html", users=all_users, search_query=search_query
    )


def get_top_drink_for_period(start_date=None):
    query = db.session.query(
        Drink, func.count(DrunkAction.id).label("orders_count")
    ).join(DrunkAction, DrunkAction.drink_id == Drink.id)

    if start_date:
        query = query.filter(DrunkAction.timestamp >= start_date)
    result = (
        query.group_by(Drink.id).order_by(func.count(DrunkAction.id).desc()).first()
    )
    return result if result else (None, 0)


def get_top_bar_for_period(start_date=None):
    query = (
        db.session.query(Bar, func.count(DrunkAction.id).label("visits_count"))
        .join(Drink, Drink.bar_id == Bar.id)
        .join(DrunkAction, DrunkAction.drink_id == Drink.id)
    )

    if start_date:
        query = query.filter(DrunkAction.timestamp >= start_date)

    result = query.group_by(Bar.id).order_by(func.count(DrunkAction.id).desc()).first()
    return result if result else (None, 0)


@main.route("/metrics/")
@login_required
def metrics():
    now = datetime.utcnow()

    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)
    year_ago = now - timedelta(days=365)

    user_fav_drink = None
    user_fav_percentage = 0

    if current_user.is_authenticated:
        user_logs = (
            db.session.query(Drink, func.count(DrunkAction.id).label("c"))
            .join(DrunkAction, DrunkAction.drink_id == Drink.id)
            .filter(DrunkAction.user_id == current_user.id)
            .group_by(Drink.id)
            .order_by(func.count(DrunkAction.id).desc())
            .all()
        )

        if user_logs:
            total_user_drinks = sum(log.c for log in user_logs)
            user_fav_drink = user_logs[0][0]
            if total_user_drinks > 0:
                user_fav_percentage = int((user_logs[0][1] / total_user_drinks) * 100)

    # 2. АГРЕГАЦИЯ ТОП НАПИТКОВ СООБЩЕСТВА
    drink_moment, count_dm = get_top_drink_for_period(day_ago)
    drink_month, count_dmo = get_top_drink_for_period(month_ago)
    drink_year, count_dy = get_top_drink_for_period(year_ago)
    drink_all, count_da = get_top_drink_for_period(None)

    # 3. АГРЕГАЦИЯ ТОП БАРОВ СООБЩЕСТВА
    bar_moment, count_bm = get_top_bar_for_period(day_ago)
    bar_month, count_bmo = get_top_bar_for_period(month_ago)
    bar_year, count_by = get_top_bar_for_period(year_ago)
    bar_all, count_ba = get_top_bar_for_period(None)

    community_metrics = {
        "drinks": {
            "moment": {"object": drink_moment, "value": count_dm},
            "month": {"object": drink_month, "value": count_dmo},
            "year": {"object": drink_year, "value": count_dy},
            "all_time": {"object": drink_all, "value": count_da},
        },
        "bars": {
            "moment": {"object": bar_moment, "value": count_bm},
            "month": {"object": bar_month, "value": count_bmo},
            "year": {"object": bar_year, "value": count_by},
            "all_time": {"object": bar_all, "value": count_ba},
        },
    }

    return render_template(
        "metrics.html",
        user_fav_drink=user_fav_drink,
        user_fav_percentage=user_fav_percentage,
        cm=community_metrics,
    )


@main.route("/bars/", methods=["GET"])
@login_required
def get_bars_list():
    options = [
        r[0] for r in db.session.query(Drink.type).distinct().all() if r and r[0]
    ]
    cities = [r[0] for r in db.session.query(Bar.city).distinct().all() if r and r[0]]

    default_city = "any"
    if "city" not in request.args:
        if current_user.is_authenticated and current_user.location:
            if current_user.location in cities:
                default_city = current_user.location
            else:
                default_city = random.choice(cities) if cities else "any"
        else:
            default_city = random.choice(cities) if cities else "any"

    city_val = request.args.get("city", default_city)
    drink_type = request.args.get("type", "any")
    rating_val = request.args.get("rating", "any")
    distance_val = request.args.get("distance", "any")
    open_now = request.args.get("open_now") == "true"

    query = Bar.query

    if city_val != "any":
        query = query.filter(Bar.city == city_val)

    if drink_type != "any":
        query = query.join(Drink).filter(Drink.type == drink_type)
        query = query.order_by(Drink.score.asc())
    else:
        query = query.order_by(Bar.rate.asc())

    if rating_val != "any":
        try:
            query = query.filter(Bar.rate >= float(rating_val))
        except ValueError:
            pass

    bars = query.distinct().all()

    return render_template(
        "bars.html",
        options=options,
        cities=cities,
        bars=bars,
        current_city=city_val,
    )


@main.route("/add_bar/", methods=["GET", "POST"])
@login_required
@admin_required
def add_bar():
    if request.method == "POST":
        bar = Bar()
        bar.name = request.form["name"]
        bar.city = request.form["city"]
        bar.address = request.form["address"]
        bar.admin_id = (
            current_user.id
        )
        db.session.add(bar)
        db.session.commit()
        flash("The bar has been created.")
        redirect(url_for("main.get_bars_list"))
    return render_template("/creators/create_bar.html")


@main.route("/edit_bar/<int:id>", methods=["GET", "POST"])
@login_required
def edit_bar(id):
    bar = Bar.query.get_or_404(id)
    if request.method == "POST":
        bar.name = request.form["name"]
        bar.admin_id = request.form["admin_id"]
        bar.address = request.form["address"]
        bar.rate = bar.get_bar_rate()
        db.session.add(bar)
        db.session.commit()
        flash("The bar has been changed.")
        return redirect(url_for("main.get_bars_list"))
    qr_base64 = None
    if bar.qr_secret_hash:
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(bar.qr_secret_hash)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")

        qr_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return render_template(
        "editors/edit_bar.html", editing_bar=bar, qr_base64=qr_base64
    )


@main.route("/generate-bar-qr/<int:id>", methods=["POST"])
@login_required
def generate_bar_qr(id):
    bar = Bar.query.get_or_404(id)
    if current_user.role == "manager" and bar.admin_id != current_user.id:
        flash("Доступ запрещен.", "danger")
        return redirect(url_for("main.user", username=current_user.username))
    elif current_user.role == "user":
        abort(403)

    bar.qr_secret_hash = secrets.token_hex(32)
    db.session.commit()

    flash(
        f'Криптографический секрет для заведения "{bar.name}" успешно сгенерирован.',
        "success",
    )
    return redirect(request.referrer or url_for("main.get_bar_drinks", id=bar.id))


@main.route("/drinks/", methods=["GET"])
@login_required
def get_drinks_list():
    page = request.args.get("page", 1, type=int)
    selected_type = request.args.get("type", "any")
    selected_rating = request.args.get("rating", "any")

    filter_args = {k: v for k, v in request.args.items() if k != "page"}

    query = (
        db.session.query(
            Drink,
            func.coalesce(func.avg(DrinkRating.value), 0.0).label("average_rating"),
        )
        .outerjoin(DrinkRating)
        .group_by(Drink.id)
    )

    if selected_type != "any":
        query = query.filter(Drink.type == selected_type)

    if selected_rating != "any":
        try:
            rating_limit = float(selected_rating)
            query = query.having(
                func.coalesce(func.avg(DrinkRating.value), 0.0) >= rating_limit
            )
        except ValueError:
            pass

    query = query.order_by(func.avg(DrinkRating.value).desc())

    pagination = query.paginate(
        page=page, per_page=Config.DRINKS_PER_PAGE, error_out=False
    )
    drinks = []
    for drink_obj, avg_rating in pagination.items:
        drink_obj.rating = (
            avg_rating
        )
        drinks.append(drink_obj)

    options = [
        row[0] for row in db.session.query(Drink.type).distinct().all() if row[0]
    ]

    return render_template(
        "drinks.html",
        drinks=drinks,
        pagination=pagination,
        options=options,
        filter_args=filter_args,  # Передаем очищенный словарь в HTML
    )


@main.route("/delete_bar/<int:bar_id>", methods=["POST"])
@login_required
@admin_required
def delete_bar(bar_id):
    bar = Bar.query.get_or_404(bar_id)
    db.session.delete(bar)
    db.session.commit()

    flash("Бар был успешно удален из системы.", "success")

    return redirect(url_for("main.get_bars_list"))


@main.route("/bar/<int:id>", methods=["GET"])
@login_required
def get_bar_drinks(id):
    bar = Bar.query.get_or_404(id)
    return render_template("/includes/bar_drinks.html", bar=bar)


@main.route("/add_drink/", methods=["GET", "POST"])
@login_required
def add_drink():
    bar_id = request.args.get("bar_id", type=int)
    if bar_id:
        bar = Bar.query.get_or_404(bar_id)

        if current_user.role == "manager" and bar.admin_id != current_user.id:
            flash(
                "Доступ запрещен. Вы можете расширять ассортимент только своего бара.",
                "danger",
            )
            return redirect(url_for("main.get_bar_drinks", id=bar.id))

        elif current_user.role == "user":
            abort(403)
    else:
        if current_user.role != "administrator":
            abort(403)

    if request.method == "POST":
        drink = Drink()
        drink.name = request.form.get("name", "").strip()
        drink.type = request.form.get("type", "Cocktail")
        drink.description = request.form.get("description", "")

        try:
            drink.volume = int(request.form.get("volume", 0))
        except (ValueError, TypeError):
            drink.volume = 0

        try:
            drink.abv = float(request.form.get("abv", 0.0))
        except (ValueError, TypeError):
            drink.abv = 0.0

        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
                file.save(file_path)
                drink.image_path = filename
                if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                    file.seek(0)
                    with open(file_path, "wb") as f:
                        f.write(file.read())

        if bar_id:
            drink.bar_id = bar_id

        db.session.add(drink)
        db.session.commit()
        flash("Напиток успешно добавлен в меню!", "success")

        if bar_id:
            return redirect(url_for("main.get_bar_drinks", id=bar_id))
        return redirect(url_for("main.get_drinks_list"))

    return render_template("/creators/create_drink.html", bar_id=bar_id)


@main.route("/drink/<int:drink_id>/edit/", methods=["GET", "POST"])
@login_required
def edit_drink(drink_id):
    drink = Drink.query.get_or_404(drink_id)

    if request.method == "POST":
        drink.name = request.form.get("name", "").strip()
        drink.type = request.form.get("type", "Cocktail")
        drink.description = request.form.get("description", "")

        try:
            drink.volume = int(request.form.get("volume", 0))
        except (ValueError, TypeError):
            drink.volume = 0

        try:
            drink.abv = float(request.form.get("abv", 0.0))
        except (ValueError, TypeError):
            drink.abv = 0.0

        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                new_file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
                if drink.image_path:
                    old_file_path = os.path.join(Config.UPLOAD_FOLDER, drink.image_path)
                    if os.path.exists(old_file_path):
                        try:
                            os.remove(old_file_path)
                        except Exception as e:
                            print(f"Ошибка удаления старого файла: {e}", flush=True)

                os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                file.save(new_file_path)

                drink.image_path = filename
            elif file and file.filename != "":
                flash("Недопустимый формат файла.", "danger")

        db.session.commit()
        flash("Напиток успешно обновлен!", "success")

        if drink.bar_id:
            return redirect(url_for("main.get_bar_drinks", id=drink.bar_id))
        return redirect(url_for("main.get_drinks_list"))

    return render_template("/creators/edit_drink.html", drink=drink)


@main.route("/drink/<int:drink_id>/toggle-favorite", methods=["POST"])
@login_required
def toggle_drink_favorite(drink_id):
    drink = Drink.query.get_or_404(drink_id)

    if drink in current_user.favorite_drinks.all():
        current_user.favorite_drinks.remove(drink)
        flash(f"Напиток «{drink.name}» удален из избранного.", "info")
    else:
        current_user.favorite_drinks.append(drink)
        flash(f"Напиток «{drink.name}» добавлен в избранное!", "success")

    db.session.commit()
    return redirect(request.referrer or url_for(".get_drinks_list"))


def calculate_monthly_badge(user):
    month_ago = datetime.utcnow() - timedelta(days=30)
    monthly_logs = user.drunk_history.filter(DrunkAction.timestamp >= month_ago).all()

    if not monthly_logs:
        return "Трезвенник"

    total_beer_volume = 0
    total_strong_volume = 0

    for log in monthly_logs:
        if log.drink.type.lower() == "пиво":
            total_beer_volume += log.drink.volume
        elif float(log.drink.abv) >= 30.0:
            total_strong_volume += log.drink.volume

    if total_beer_volume >= 5000:
        return "ПИВО"
    elif total_strong_volume >= 1000:
        return "Пират"

    return "Любитель"


@main.route("/drink/<int:drink_id>/add-drunk", methods=["POST"])
@login_required
def add_drink_drunk(drink_id):
    drink = Drink.query.get_or_404(drink_id)
    now = datetime.utcnow()

    last_action = (
        current_user.drunk_history.filter_by(drink_id=drink.id)
        .order_by(DrunkAction.timestamp.desc())
        .first()
    )
    if last_action:
        cooldown_seconds = 10
        time_passed = now - last_action.timestamp

        if time_passed < timedelta(seconds=cooldown_seconds):
            remaining_time = cooldown_seconds - int(time_passed.total_seconds())
            flash(
                f"Подождите еще {remaining_time} сек. перед тем как отметить следующий бокал!",
                "danger",
            )
            return redirect(request.referrer or url_for(".get_drinks_list"))
    new_action = DrunkAction(user_id=current_user.id, drink_id=drink.id)
    db.session.add(new_action)

    current_user.log_action(
        action_type="drink_alcohol",
        description=f"Вы отметили, что выпили «{drink.name}» ({drink.volume}мл, {drink.abv}%)",
    )
    flash(f"«{drink.name}» добавлен в вашу историю выпитого!", "success")
    db.session.commit()
    return redirect(request.referrer or url_for(".get_drinks_list"))


@main.route("/drink/<int:drink_id>/rate", methods=["POST"])
@login_required
def rate_drink(drink_id):
    drink = Drink.query.get_or_404(drink_id)
    if not current_user.is_drink_drunk(drink.id):
        flash(
            "Вы не можете оценивать напиток, пока не добавите его в «Выпитые».",
            "danger",
        )
        return redirect(request.referrer or url_for(".get_drinks_list"))

    try:
        rating_value = int(request.form.get("value"))
        if rating_value < 1 or rating_value > 5:
            raise ValueError
    except (ValueError, TypeError):
        flash("Некорректное значение оценки.", "danger")
        return redirect(request.referrer or url_for(".index"))

    existing_rating = DrinkRating.query.filter_by(
        user_id=current_user.id, drink_id=drink.id
    ).first()

    if existing_rating:
        existing_rating.value = rating_value
        current_user.log_action(
            action_type="rate_drink",
            description=f"Вы изменили оценку напитку «{drink.name}» на {rating_value}★",
        )
        flash(f"Оценка напитка {drink.name} обновлена.", "success")
    else:
        new_rating = DrinkRating(
            user_id=current_user.id, drink_id=drink.id, value=rating_value
        )
        db.session.add(new_rating)
        current_user.log_action(
            action_type="rate_drink",
            description=f"Вы поставили оценку напитку «{drink.name}» ({rating_value}★)",
        )
        flash(f"Вы оценили напиток {drink.name} на {rating_value}★!", "success")

    db.session.flush()
    drink.update_rating()

    db.session.commit()
    return redirect(url_for("main.get_drinks_list"))


@main.route("/delete_drink/<int:drink_id>", methods=["POST"])
@login_required
def delete_drink(drink_id):
    drink = Drink.query.get_or_404(drink_id)
    db.session.delete(drink)
    db.session.commit()

    flash("Напиток был успешно удален из системы.")

    return redirect(request.referrer or url_for("main.get_drinks_list"))


@main.route("/favorite/toggle/<int:bar_id>", methods=["POST"])
@login_required
def toggle_favorite(bar_id):
    bar = Bar.query.get_or_404(bar_id)
    is_favorite = current_user.favorite_bars.filter_by(id=bar.id).first() is not None

    if is_favorite:
        current_user.favorite_bars.remove(bar)
        current_user.log_action(
            action_type="favorite_remove",
            description=f"Вы удалили заведение «{bar.name}» из избранного",
        )
        flash(f"Заведение {bar.name} удалено из избранного.", "info")
    else:
        current_user.favorite_bars.append(bar)
        current_user.log_action(
            action_type="favorite_add",
            description=f"Вы добавили заведение «{bar.name}» в избранное",
        )
        flash(f"Заведение {bar.name} добавлено в избранное!", "success")

    db.session.commit()
    return redirect(request.referrer or url_for(".index"))
