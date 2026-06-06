from flask import jsonify, g
from . import api
from ..models import Drink, User
#from .decorators import login_required  # или твой декоратор авторизации


@api.route('/user/profile')
# @login_required # Раскомментируй, когда подключишь проверку g.current_user
def get_user_profile():
    # Для теста берем пользователя, под которым ты зашел (например, id=3)
    # В реальном коде тут должно быть: user = g.current_user
    user = User.query.get_or_404(3)

    # Считаем количество напитков, которые привязаны к барам этого менеджера
    # Или просто общее количество созданных им позиций
    total_drinks = Drink.query.filter_by(bar_id=1).count()  # Пример логики статистики

    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': getattr(user, 'email', 'manager@brs.com'),  # подстраховка, если нет email в модели
        'role': user.type,  # 'manager' или 'user' из твоего полиморфизма
        'stats': {
            'total_drinks_managed': total_drinks,
            'favorite_category': 'Cocktail',
            'registered_at': '2026-05-28'  # Любая заглушка даты или реальное поле
        }
    })