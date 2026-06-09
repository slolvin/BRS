from flask import jsonify, request, g, url_for, current_app
from .. import db
from ..models import Drink, Permission, DrinkRating
from flask_login import current_user, login_required
from sqlalchemy import func
from . import api
from .decorators import permission_required
from .errors import forbidden


@api.route('/drinks/')
def get_drinks():
    page = request.args.get('page', 1, type=int)
    # Используем стандартный лимит из конфига, убираем странный +2 для предсказуемости iOS-сеток
    per_page = current_app.config.get('DRINKS_PER_PAGE', 10)

    pagination = Drink.query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    drinks = pagination.items

    # Формируем базовый URL сервера для картинок (iOS нужен полный путь!)
    # request.host_url вернет что-то вроде http://192.168.1 (в зависимости от сети)
    base_url = request.host_url.rstrip('/')

    # Сериализуем данные, на лету добавляя абсолютный путь к фото для Xcode
    json_drinks = []
    for drink in drinks:
        drink_data = drink.to_json()
        if drink_data.get('image'):
            drink_data['image_url'] = f"{base_url}/static/drinks/{drink_data['image']}"
        else:
            drink_data['image_url'] = None
        json_drinks.append(drink_data)

    # Отдаем идеальный для Swift-структур (Decodable) ответ
    return jsonify({
        'drinks': json_drinks,
        'current_page': page,
        'per_page': per_page,
        'total_pages': pagination.pages,
        'has_prev': pagination.has_prev,
        'has_next': pagination.has_next,
        'count': pagination.total
    })


# @api.route('/drinks/<int:id>')
# def get_drink(id):
#     drink = Drink.query.get_or_404(id)
#     drink_data = drink.to_json()
#
#     # Также собираем абсолютный URL для одиночного запроса
#     base_url = request.host_url.rstrip('/')
#     if drink_data.get('image'):
#         drink_data['image_url'] = f"{base_url}/static/drinks/{drink_data['image']}"
#     else:
#         drink_data['image_url'] = None
#
#     return jsonify(drink_data)


@api.route('/drinks/<int:id>', methods=['GET'])
# @login_required  # Защищаем ручку сессией авторизации
def get_drink(id):
    # 1. Ищем напиток по id. Если его нет — вернется чистый 404 Not Found
    drink = Drink.query.get_or_404(id)

    # 2. Базовый URL для сборки абсолютного пути к картинке
    base_url = request.host_url.rstrip('/')

    # 3. Сериализуем через родной метод модели
    drink_data = drink.to_json()

    # 4. Проверяем имя картинки (из модели или словаря) и собираем url для UIImageView
    image_name = drink.image_path or drink_data.get('image') or drink_data.get('image_path')

    if image_name:
        drink_data['image_url'] = f"{base_url}/static/drinks/{image_name}"
    else:
        drink_data['image_url'] = None

    # На всякий случай удаляем сырое имя файла, чтобы не путать Swift-клиент
    drink_data.pop('image_path', None)
    drink_data.pop('image', None)

    # 5. Отдаем готовый JSON со статусом 200 OK
    return jsonify(drink_data), 200


@api.route('/drinks/<int:id>/rate', methods=['POST'])
# @login_required  # Оценивать могут только авторизованные пользователи
def rate_drink(id):
    # 1. Ищем напиток в базе
    drink = Drink.query.get_or_404(id)

    # 2. Получаем JSON из Swift
    json_data = request.get_json()
    if not json_data or 'rating' not in json_data:
        return jsonify({'error': 'Bad Request', 'message': 'Отсутствует поле rating'}), 400

    try:
        new_rating = int(json_data['rating'])
        if new_rating < 1 or new_rating > 5:
            return jsonify({'error': 'Validation Error', 'message': 'Оценка должна быть от 1 до 5'}), 422
    except ValueError:
        return jsonify({'error': 'Validation Error', 'message': 'Оценка должна быть целым числом'}), 422

    try:
        # 3. ЛОГИКА ПЕРЕСЧЕТА (Без таблицы оценок):
        # Если у напитка еще нет рейтинга (score равен None или 0)
        if not drink.score or float(drink.score) == 0.0:
            drink.score = float(new_rating)
        else:
            # «Мягкое» обновление рейтинга (алгоритм экспоненциального сглаживания):
            # Новая оценка влияет на общий рейтинг с определенным весом (например, 20%)
            # Это позволяет рейтингу плавно изменяться, имитируя присутствие других оценок
            current_score = float(drink.score)
            weight = 0.2  # Коэффициент влияния новой оценки (чем меньше, тем тяжелее изменить рейтинг)

            updated_score = (current_score * (1 - weight)) + (new_rating * weight)
            drink.score = round(updated_score, 2)

        # 4. Сохраняем изменения в текущую таблицу drinks
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

    # 5. Возвращаем новый score в iOS для мгновенного обновления звездочек
    return jsonify({
        'status': 'success',
        'message': 'Оценка учтена',
        'new_score': float(drink.score)
    }), 200