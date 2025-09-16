from flask import render_template, redirect, url_for, abort, flash, request, current_app, make_response
from flask_login import login_required, current_user
from . import main
# from .forms import NameForm
from .. import db
from ..models import User, Role, Permission


@main.route('/user/<username>')
@login_required
def user(username):
    this_user = User.query.filter_by(username=username).first_or_404()
    return render_template('user.html', user=this_user)


@main.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.location = request.form['location']
        current_user.email  =  request.form['email']
        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    return render_template('edit_profile.html')


@main.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')
    # form = NameForm()
    # if form.validate_on_submit():
    #     # ...
    #     return redirect(url_for('.index'))
    # return render_template('index.html',
    #                        form=form, name=session.get('name'),
    #                        know=session.get('know', False),
    #                        current_time=datetime.utcnow())
