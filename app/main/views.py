from flask import render_template, redirect, url_for, abort, flash, request, current_app, make_response
from flask_login import login_required, current_user
from . import main
from .forms import EditProfileAdminForm
from .. import db
from ..models import User, Role, Permission, Bar, Drink


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
        current_user.email = request.form['email']
        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    return render_template('edit_profile.html')


# @main.route('/', methods=['GET', 'POST'])
# def index():
#     redirect(url_for('get_bars_list'))
#     # form = NameForm()
    # if form.validate_on_submit():
    #     # ...
    #     return redirect(url_for('.index'))
    # return render_template('index.html',
    #                        form=form, name=session.get('name'),
    #                        know=session.get('know', False),
    #                        current_time=datetime.utcnow())

@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
# @admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.email = request.form['email']
        user.username = request.form['username']
        # user.confirmed = form.confirmed.data
        user.role = Role.query.get(request.form['role'])
        user.name = request.form['name']
        user.location = request.form['location']
        user.about_me = request.form['about_me']
        db.session.add(user)
        db.session.commit()
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    return render_template('edit_profile_admin.html', editing_user=user)


@main.route('/')
def index():
    return redirect(url_for('.get_bars_list'))


@main.route('/bars/', methods=['GET', 'POST'])
def get_bars_list():
    options = ['Water', 'Beer', 'Vodka', 'Wiskey', 'Cocktail']
    bars = Bar.query.order_by(Bar.rate.asc()).distinct().all()
    if request.method == 'POST':
        drink = request.form['type']
        bars = Bar.query.join(Drink).filter(Drink.type == drink).order_by(Drink.score).all()
        return render_template('bars.html', options=options, bars=bars)
    return render_template('bars.html', options=options, bars=bars)


@main.route('/add_bar/', methods=['GET', 'POST'])
def add_bar():
    if request.method == 'POST':
        bar = Bar()
        bar.name = request.form['name']
        bar.city = request.form['city']
        bar.address = request.form['address']
        bar.admin_id = current_user.id # if user not in admin list he can't add bars (bug or feature?)
        db.session.add(bar)
        db.session.commit()
        flash('The bar has been created.')
        redirect(url_for('main.get_bars_list'))
    return render_template('/creators/create_bar.html')


@main.route('/edit_bar/<int:id>', methods=['GET', 'POST'])
def edit_bar(id):
    bar = Bar.query.get_or_404(id)
    if request.method == 'POST':
        bar.name = request.form['name']
        bar.admin_id = request.form['admin_id']
        bar.address = request.form['address']
        bar.rate = bar.get_bar_rate()
        db.session.add(bar)
        db.session.commit()
        flash('The bar has been changed.')
        return redirect(url_for('main.get_bars_list'))
    return render_template('editors/edit_bar.html', editing_bar=bar)


@main.route('/drinks/', methods=['GET'])
def get_drinks_list():
    drinks = Drink.query.order_by(Drink.score).all()
    return render_template('drinks.html', drinks=drinks)


@main.route('/bar/<int:id>', methods=['GET'])
@login_required
def get_bar_drinks(id):
    bar = Bar.query.get_or_404(id)
    return render_template('/includes/bar_drinks.html', bar=bar)


@main.route('/add_drink/', methods=['GET', 'POST'])
def add_drink():
    if request.method == 'POST':
        drink = Drink()
        drink.name = request.form['name']
        drink.type = request.form['type']
        drink.description = request.form['description']
        db.session.add(drink)
        db.session.commit()
        flash('The drink has been created.')
        redirect(url_for('main.get_drinks_list'))
    return render_template('/creators/create_drink.html')


@main.route('/rate/<int:drink_id>', methods=['POST'])
def rate_drink(drink_id):
    drink = Drink.query.get_or_404(drink_id)
    drink.score = int(request.form['rate'])
    db.session.add(drink)
    db.session.commit()
    # bar = Drink.query.get_or_404(drink.bar_id)
    # bar.rate = bar.get_bar_rate()
    # db.session.add(bar)
    # db.session.commit()
    return redirect(url_for('main.get_drinks_list'))
