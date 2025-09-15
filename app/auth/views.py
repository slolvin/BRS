from flask import render_template, redirect, request, url_for, flash
from flask_login import logout_user, login_user, login_required, current_user
from . import auth
from .. import db
from ..models import User
from .forms import LoginForm, RegistrationForm


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user is not None and user.verify_password(request.form['password']):
            ## Add remember me checkbox ##
            login_user(user)
            next_view = request.args.get('next')
            if next_view is None or not next_view.startswith('/'):
                next_view = url_for('main.index')
            return redirect(next_view)
        flash('Invalid username or password.')
    return render_template('auth/login2.html')

    # form = LoginForm()
    # if form.validate_on_submit():
    #     user = User.query.filter_by(email=form.email.data).first()
    #     if user is not None and user.verify_password(form.password.data):
    #         login_user(user, form.remember_me.data)
    #         return redirect(request.args.get('next') or url_for('main.index'))
    #     flash('Invalid username or password.')
    # return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('main.index'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User(email=request.form['email'],
                    username=request.form['username'],
                    password=request.form['password'])
        db.session.add(user)
        db.session.commit()
        # INSERT HERE SEND EMAIL SECTION #
        flash('You can now login.')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')
    # form = RegistrationForm()
    # if form.validate_on_submit():
    #     user = User(email=form.email.data,
    #                 username=form.username.data,
    #                 password=form.password.data)
    #     db.session.add(user)
    #     db.session.commit()
    #     # INSERT HERE SEND EMAIL SECTION #
    #     flash('You can now login.')
    #     return redirect(url_for('auth.login'))
    # return render_template('auth/register.html', form=form)


# @auth.before_app_request
# def before_request():
#     if current_user.is_authenticated() and not current_user.confirmed and request.endpoint[:5] != 'auth.':
#         return redirect(url_for('auth.unconfirmed'))
#
#
# @auth.route('/unconfirmed')
# def unconfirmed():
#     if current_user.is_anonymous() or current_user.confirmed:
#         return redirect('main.index')
#     return render_template('auth/unconfirmed.html')
