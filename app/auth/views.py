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


@auth.route("/unconfirmed")
@login_required
def unconfirmed():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("auth/unconfirmed.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = True if request.form.get("remember_me") else False
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

@auth.route("/register", methods=["GET", "POST"])
def register():
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

        user = User(email=email, username=username, password=password)

        db.session.add(user)
        db.session.commit()

        flash("Регистрация прошла успешно! Теперь вы можете войти.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth.route("/register_manager", methods=["GET", "POST"])
@login_required
@admin_required
def register_manager():
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

        manager_user = User(
            email=email,
            username=username,
            password=password,
            role="manager",
        )

        db.session.add(manager_user)
        db.session.commit()

        flash(f"Учетная запись менеджера @{username} успешно создана!", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/register_manager.html")
