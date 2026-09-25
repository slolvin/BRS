from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .. import db
from ..decorators import admin_required
from ..models import User
from . import auth


@auth.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.ping()
        # Если в будущем решите вернуть подтверждение почты (confirmed):
        # if not current_user.confirmed \
        #         and request.endpoint \
        #         and request.blueprint != 'auth' \
        #         and request.endpoint != 'static':
        #     return redirect(url_for('auth.unconfirmed'))


@auth.route("/unconfirmed")
@login_required  # Страница unconfirmed имеет смысл только для залогиненных, но не подтвержденных юзеров
def unconfirmed():
    # Если пользователь уже подтвержден (заглушка: пока просто пускаем всех залогиненных на главную)
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("auth/unconfirmed.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = True if request.form.get("remember_me") else False

        # ИСПРАВЛЕНО: Теперь возвращается чистый объект User со строковой ролью внутри поля .role
        user = User.query.filter_by(email=email).first()

        if user is not None and user.verify_password(password):
            login_user(user, remember=remember)

            next_view = request.args.get("next")
            if next_view is None or not next_view.startswith("/"):
                next_view = url_for("main.index")
            return redirect(next_view)

        flash("Неверный email или пароль.", "danger")

    return render_template("auth/login2.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы успешно вышли из системы.", "success")
    return redirect(url_for("main.index"))


# Не забудьте импортировать ваш новый декоратор из файла, где он объявлен
# Например: from ..decorators import admin_required
# Или если он в текущем пакете, настройте импорт правильно.


@auth.route("/register", methods=["GET", "POST"])
def register():
    """Публичная регистрация для обычных пользователей (клиентов)"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if User.query.filter_by(email=email).first():
            flash("Этот email уже зарегистрирован.", "danger")
            return render_template("auth/register.html")

        if User.query.filter_by(username=username).first():
            flash("Это имя пользователя уже занято.", "danger")
            return render_template("auth/register.html")

        # Роль явно НЕ указываем — сработает default='user' из модели базы данных
        user = User(email=email, username=username, password=password)

        db.session.add(user)
        db.session.commit()

        flash("Регистрация прошла успешно! Теперь вы можете войти.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth.route("/register_manager", methods=["GET", "POST"])
@login_required
@admin_required  # <-- ЖЕСТКАЯ ЗАЩИТА: Сюда может зайти ТОЛЬКО Администратор
def register_manager():
    """Закрытая регистрация менеджеров баров силами Администратора"""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if User.query.filter_by(email=email).first():
            flash("Этот email уже используется.", "danger")
            return render_template("auth/register_manager.html")

        if User.query.filter_by(username=username).first():
            flash("Это имя пользователя уже занято.", "danger")
            return render_template("auth/register_manager.html")

        # ЯВНО ПРИСВАИВАЕМ РОЛЬ МЕНЕДЖЕРА
        manager_user = User(
            email=email,
            username=username,
            password=password,
            role="manager",  # <-- Вот здесь фиксируем статус управляющего
        )

        db.session.add(manager_user)
        db.session.commit()

        flash(f"Учетная запись менеджера @{username} успешно создана!", "success")
        # После создания возвращаем админа либо на главную, либо в панель управления
        return redirect(url_for("main.index"))

    return render_template("auth/register_manager.html")
