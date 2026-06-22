from flask import render_template, redirect, url_for, abort, flash, request, current_app, make_response
from flask_login import login_required, current_user
from sqlalchemy import func
from . import main
from .forms import EditProfileAdminForm
from .. import db
from ..models import User, Role, Permission, Bar, Drink, ActionLog, DrinkRating
from config import Config
import os
import random
from werkzeug.utils import secure_filename


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@main.route('/user/<username>')
@login_required
def user(username):
    this_user = User.query.filter_by(username=username).first_or_404()

    # Получаем последние 10 действий именно ЭТОГО пользователя
    user_logs = this_user.actions.order_by(ActionLog.timestamp.desc()).limit(10).all()

    # Получаем ВСЕ любимые бары ЭТОГО пользователя
    favorite_bars = this_user.favorite_bars.all()

    return render_template(
        'user.html',
        user=this_user,
        user_logs=user_logs,
        favorite_bars=favorite_bars
    )


@main.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    # ИСПРАВЛЕНО: берем логи и любимые бары прямо из текущего залогиненного пользователя
    user_logs = current_user.actions.order_by(ActionLog.timestamp.desc()).limit(10).all()
    favorite_bars = current_user.favorite_bars.all()

    if request.method == 'POST':
        current_user.name = request.form['name']
        current_user.location = request.form['location']
        current_user.email = request.form['email']

        # Добавляем лог действия
        current_user.log_action(
            action_type='edit_profile',
            description='Вы обновили данные своего профиля'
        )

        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))

    # Возвращаем шаблон редактирования, передавая туда все необходимые списки
    return render_template('edit_profile.html',
                           user=current_user,
                           user_logs=user_logs,
                           favorite_bars=favorite_bars)


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


@main.route('/metrics/')
def metrics():
    # Пока отдаем пустую заглушку, как мы сверстали
    return render_template('metrics.html')


@main.route('/bars/', methods=['GET'])
def get_bars_list():
    # 1. Получаем список уникальных непустых типов напитков
    options = [r[0] for r in db.session.query(Drink.type).distinct().all() if r and r[0]]

    # 2. Получаем список уникальных непустых городов, которые ЕСТЬ у баров в БД
    # Это исключит ситуацию, когда выберется город, в котором нет ни одного заведения
    cities = [r[0] for r in db.session.query(Bar.city).distinct().all() if r and r[0]]

    # 3. Определяем город по умолчанию (если параметр 'city' еще не передан в URL)
    default_city = 'any'
    if 'city' not in request.args:
        if current_user.is_authenticated and current_user.location:
            # Проверяем, есть ли город пользователя среди городов, где вообще есть бары
            if current_user.location in cities:
                default_city = current_user.location
            else:
                # Если у юзера редкий город, где баров нет, берем случайный из доступных
                default_city = random.choice(cities) if cities else 'any'
        else:
            # Юзер не залогинен или у него нет города — берем случайный из базы баров
            default_city = random.choice(cities) if cities else 'any'

    # 4. Считываем параметры фильтрации из URL (если 'city' нет, подставляем наш default_city)
    city_val = request.args.get('city', default_city)
    drink_type = request.args.get('type', 'any')
    rating_val = request.args.get('rating', 'any')
    distance_val = request.args.get('distance', 'any')
    open_now = request.args.get('open_now') == 'true'

    # 5. Инициализируем базовый запрос к барам
    query = Bar.query

    # 6. Фильтр по городу
    if city_val != 'any':
        query = query.filter(Bar.city == city_val)

    # 7. Фильтр по типу напитка и сортировка
    if drink_type != 'any':
        query = query.join(Drink).filter(Drink.type == drink_type)
        query = query.order_by(Drink.score.asc())
    else:
        query = query.order_by(Bar.rate.asc())

    # 8. Фильтр по рейтингу бара
    if rating_val != 'any':
        try:
            query = query.filter(Bar.rate >= float(rating_val))
        except ValueError:
            pass

    # 9. Выполняем и убираем дубликаты баров
    bars = query.distinct().all()

    return render_template(
        'bars.html',
        options=options,
        cities=cities,
        bars=bars,
        current_city=city_val  # Передаем вычисленный город, чтобы подсветить его в select
    )


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
    page = request.args.get('page', 1, type=int)
    selected_type = request.args.get('type', 'any')
    selected_rating = request.args.get('rating', 'any')

    # 1. Формируем плоский словарь параметров для безопасной пагинации
    # Это полностью решает проблему ошибки в url_for(..., **kwargs)
    filter_args = {k: v for k, v in request.args.items() if k != 'page'}

    # 2. Начинаем запрос с подсчетом средней оценки для каждого напитка из DrinkRating
    # Группируем по Drink.id, чтобы посчитать среднее (func.avg)
    query = db.session.query(
        Drink,
        func.coalesce(func.avg(DrinkRating.value), 0.0).label('average_rating')
    ).outerjoin(DrinkRating).group_by(Drink.id)

    # 3. Фильтр по типу напитка
    if selected_type != 'any':
        query = query.filter(Drink.type == selected_type)

    # 4. Фильтр по средней оценке из связанной таблицы DrinkRating
    if selected_rating != 'any':
        try:
            rating_limit = float(selected_rating)
            # Фильтруем сгруппированный результат через HAVING
            query = query.having(func.coalesce(func.avg(DrinkRating.value), 0.0) >= rating_limit)
        except ValueError:
            pass

    # 5. Сортируем от высшей оценки к низшей
    query = query.order_by(func.avg(DrinkRating.value).desc())

    # 6. Применяем пагинацию SQLAlchemy
    pagination = query.paginate(
        page=page,
        per_page=Config.DRINKS_PER_PAGE,
        error_out=False
    )

    # ВАЖНО: Из-за кастомного query со средним баллом, pagination.items теперь содержит кортежи: (Объект_Drink, средний_балл)
    # Чтобы не ломать ваши шаблоны, мы динамически запишем средний балл прямо в поле объекта!
    drinks = []
    for drink_obj, avg_rating in pagination.items:
        drink_obj.rating = avg_rating  # Записываем актуальный балл для includes/rate_drink.html
        drinks.append(drink_obj)

    # 7. Безопасное получение уникальных типов (исправлена проблема с кортежами)
    # query().all() возвращает список кортежей с одним элементом, берем row[0]
    options = [row[0] for row in db.session.query(Drink.type).distinct().all() if row[0]]

    return render_template(
        'drinks.html',
        drinks=drinks,
        pagination=pagination,
        options=options,
        filter_args=filter_args  # Передаем очищенный словарь в HTML
    )


@main.route('/delete_bar/<int:bar_id>', methods=['POST'])
@login_required
def delete_bar(bar_id):
    bar = Bar.query.get_or_404(bar_id)

    db.session.delete(bar)
    db.session.commit()

    flash('Бар был успешно удален из системы.')

    return redirect(request.referrer or url_for('main.get_bars_list'))


@main.route('/bar/<int:id>', methods=['GET'])
@login_required
def get_bar_drinks(id):
    bar = Bar.query.get_or_404(id)
    return render_template('/includes/bar_drinks.html', bar=bar)

@main.route('/add_drink/', methods=['GET', 'POST'])
def add_drink():
    bar_id = request.args.get('bar_id', type=int)

    if request.method == 'POST':
        drink = Drink()
        drink.name = request.form['name']
        drink.type = request.form['type']
        drink.description = request.form['description']

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
                file.save(file_path)
                drink.image_path = filename
                if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
                    file.seek(0)
                    with open(file_path, 'wb') as f:
                        f.write(file.read())

                drink.image_path = filename
            else:
                flash('Недопустимый формат файла.')

        if bar_id:
            drink.bar_id = bar_id

        db.session.add(drink)
        db.session.commit()

        flash('The drink has been created.')
        if bar_id:
            return redirect(url_for('main.get_bar_drinks', id=bar_id))
        return redirect(url_for('main.get_drinks_list'))

    return render_template('/creators/create_drink.html', bar_id=bar_id)


@main.route('/drink/<int:drink_id>/edit/', methods=['GET', 'POST'])
def edit_drink(drink_id):
    # Получаем существующий напиток или отдаем 404, если ID неверный
    drink = Drink.query.get_or_404(drink_id)

    if request.method == 'POST':
        drink.name = request.form['name']
        drink.type = request.form['type']
        drink.description = request.form['description']

        # Обработка обновления изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)

                # Полный путь к новому файлу
                new_file_path = os.path.join(Config.UPLOAD_FOLDER, filename)

                # Если у напитка уже было фото, удаляем старый файл с диска
                if drink.image_path:
                    old_file_path = os.path.join(Config.UPLOAD_FOLDER, drink.image_path)
                    if os.path.exists(old_file_path):
                        try:
                            os.remove(old_file_path)
                        except Exception as e:
                            print(f"Ошибка удаления старого файла: {e}", flush=True)

                # Сохраняем новую картинку
                os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                file.save(new_file_path)

                # Записываем новое имя в БД
                drink.image_path = filename

        db.session.commit()
        flash('The drink has been updated.')

        # Перенаправляем обратно в бар, если он привязан, иначе в общий список
        if drink.bar_id:
            return redirect(url_for('main.get_bar_drinks', id=drink.bar_id))
        return redirect(url_for('main.get_drinks_list'))

    return render_template('/creators/edit_drink.html', drink=drink)


@main.route('/drink/<int:drink_id>/toggle-favorite', methods=['POST'])
@login_required
def toggle_drink_favorite(drink_id):
    drink = Drink.query.get_or_404(drink_id)

    if drink in current_user.favorite_drinks.all():
        current_user.favorite_drinks.remove(drink)
        flash(f'Напиток «{drink.name}» удален из избранного.', 'info')
    else:
        current_user.favorite_drinks.append(drink)
        flash(f'Напиток «{drink.name}» добавлен в избранное!', 'success')

    db.session.commit()
    return redirect(request.referrer or url_for('.get_drinks_list'))


@main.route('/drink/<int:drink_id>/toggle-drunk', methods=['POST'])
@login_required
def toggle_drink_drunk(drink_id):
    drink = Drink.query.get_or_404(drink_id)

    if drink in current_user.drunk_drinks.all():
        current_user.drunk_drinks.remove(drink)
        flash(f'Напиток «{drink.name}» удален из списка выпитых.', 'info')
        # Опционально: если убираем из выпитых, можно удалять и оценку пользователя,
        # так как оценивать невыпитое нельзя по вашей логике
        existing_rating = DrinkRating.query.filter_by(user_id=current_user.id, drink_id=drink.id).first()
        if existing_rating:
            db.session.delete(existing_rating)
            db.session.flush()
            drink.update_rating()
    else:
        current_user.drunk_drinks.append(drink)
        flash(f'Напиток «{drink.name}» добавлен в список выпитых!', 'success')

    db.session.commit()
    return redirect(request.referrer or url_for('.get_drinks_list'))


@main.route('/drink/<int:drink_id>/rate', methods=['POST'])
@login_required
def rate_drink(drink_id):
    drink = Drink.query.get_or_404(drink_id)
    # ВАЖНОЕ ОБНОВЛЕНИЕ: Проверка на то, выпит ли напиток
    if drink not in current_user.drunk_drinks.all():
        flash('Вы не можете оценивать напиток, пока не добавите его в «Выпитые».', 'danger')
        return redirect(request.referrer or url_for('.get_drinks_list'))

    try:
        rating_value = int(request.form.get('value'))
        if rating_value < 1 or rating_value > 5:
            raise ValueError
    except (ValueError, TypeError):
        flash('Некорректное значение оценки.', 'danger')
        return redirect(request.referrer or url_for('.index'))

    existing_rating = DrinkRating.query.filter_by(user_id=current_user.id, drink_id=drink.id).first()

    if existing_rating:
        existing_rating.value = rating_value
        current_user.log_action(
            action_type='rate_drink',
            description=f'Вы изменили оценку напитку «{drink.name}» на {rating_value}★'
        )
        flash(f'Оценка напитка {drink.name} обновлена.', 'success')
    else:
        new_rating = DrinkRating(user_id=current_user.id, drink_id=drink.id, value=rating_value)
        db.session.add(new_rating)
        current_user.log_action(
            action_type='rate_drink',
            description=f'Вы поставили оценку напитку «{drink.name}» ({rating_value}★)'
        )
        flash(f'Вы оценили напиток {drink.name} на {rating_value}★!', 'success')

    # ВАЖНО: Применяем изменения в сессии, чтобы update_rating увидел новую или обновленную оценку
    db.session.flush()

    # ВЫЗОВ МЕТОДА: Пересчитываем средний балл
    drink.update_rating()

    db.session.commit()
    return redirect(url_for('main.get_drinks_list'))


@main.route('/delete_drink/<int:drink_id>', methods=['POST'])
@login_required
def delete_drink(drink_id):
    drink = Drink.query.get_or_404(drink_id)

    db.session.delete(drink)
    db.session.commit()

    flash('Напиток был успешно удален из системы.')

    return redirect(request.referrer or url_for('main.get_drinks_list'))


@main.route('/favorite/toggle/<int:bar_id>', methods=['POST'])
@login_required
def toggle_favorite(bar_id):
    # Находим бар в базе данных
    bar = Bar.query.get_or_404(bar_id)

    # Проверяем, есть ли уже этот бар в любимых (работаем как с Query благодаря lazy='dynamic')
    is_favorite = current_user.favorite_bars.filter_by(id=bar.id).first() is not None

    if is_favorite:
        # Если уже в любимых — удаляем
        current_user.favorite_bars.remove(bar)
        current_user.log_action(
            action_type='favorite_remove',
            description=f'Вы удалили заведение «{bar.name}» из избранного'
        )
        flash(f'Заведение {bar.name} удалено из избранного.', 'info')
    else:
        # Если еще нет — добавляем
        current_user.favorite_bars.append(bar)
        current_user.log_action(
            action_type='favorite_add',
            description=f'Вы добавили заведение «{bar.name}» в избранное'
        )
        flash(f'Заведение {bar.name} добавлено в избранное!', 'success')

    # Сохраняем все изменения (и связь, и лог) одной транзакцией
    db.session.commit()

    # Возвращаем пользователя туда, откуда он пришел (или на главную)
    return redirect(request.referrer or url_for('.index'))
