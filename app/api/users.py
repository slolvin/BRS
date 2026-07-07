from flask import jsonify, request
from flask_login import login_required, current_user
from .. import db
from . import api
from collections import Counter
from datetime import datetime, timedelta
from ..models import Drink, User, DrunkAction, ActionLog
#from .decorators import login_required

@api.route('/user/profile')
# @login_required
def get_user_profile():
    # В продакшене: user = g.current_user
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.get(3) or User.query.first()

    now = datetime.utcnow()
    periods = {
        'today': now.replace(hour=0, minute=0, second=0, microsecond=0),
        'week': now - timedelta(days=7),
        'month': now - timedelta(days=30),
        'year': now - timedelta(days=365),
        'all_time': datetime.min
    }

    stats = {}
    all_drunk_drinks = []  # Список для вычисления любимого напитка

    for period_name, start_date in periods.items():
        # Запрашиваем логи из DrunkAction для этого пользователя за конкретный период
        logs_query = user.drunk_history.filter(DrunkAction.timestamp >= start_date)
        count_glasses = logs_query.count()

        total_volume_liters = 0.0
        avg_abv = 0.0

        if count_glasses > 0:
            period_logs = logs_query.all()
            total_ml = sum(log.drink.volume for log in period_logs if log.drink and log.drink.volume)
            total_volume_liters = total_ml / 1000.0

            total_abv = sum(float(log.drink.abv) for log in period_logs if log.drink and log.drink.abv)
            avg_abv = total_abv / count_glasses

            if period_name == 'all_time':
                all_drunk_drinks = [log.drink for log in period_logs if log.drink]

        stats[period_name] = {
            'total_glasses': count_glasses,
            'total_liters': round(total_volume_liters, 2),
            'avg_abv': round(avg_abv, 1)
        }

    # =========================================================================
    # 2. ВЫЧИСЛЕНИЕ ЛЮБИМОГО НАПИТКА И ЗВАНИЯ МЕСЯЦА
    # =========================================================================
    fav_drink_name = "Не определен"
    if all_drunk_drinks:
        drink_counts = Counter(drink.name for drink in all_drunk_drinks if drink.name)
        if drink_counts:
            fav_drink_name = drink_counts.most_common(1)[0][0]

    # Расчет звания месяца на основе полученного словаря stats
    month_liters = stats['month']['total_liters']
    month_abv = stats['month']['avg_abv']

    if month_liters == 0:
        monthly_badge = "Трезвенник"
    elif month_liters >= 5.0 and month_abv <= 6.0:
        monthly_badge = "ПИВО"
    elif month_abv >= 30.0 and month_liters >= 1.0:
        monthly_badge = "Пират"
    else:
        monthly_badge = "Эстет"

    # Системные логи (ActionLog)
    user_logs = user.actions.order_by(ActionLog.timestamp.desc()).limit(10).all()
    logs_data = []
    for log in user_logs:
        logs_data.append({
            'action_type': log.action_type,
            'description': log.description,
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M') if log.timestamp else ''
        })

    # История выпитых коктейлей (DrunkAction)
    drunk_actions = user.drunk_history.order_by(DrunkAction.timestamp.desc()).limit(15).all()
    drunk_data = []
    for action in drunk_actions:
        if action.drink:
            drunk_data.append({
                'id': action.id,
                'drink_name': action.drink.name,
                'type': action.drink.type,
                'volume': action.drink.volume or 0,
                'abv': float(action.drink.abv) if action.drink.abv else 0.0,
                'timestamp': action.timestamp.strftime('%d.%m %H:%M') if action.timestamp else ''
            })

    # Добавляем вычисленное имя любимого напитка прямо в словарь stats, чтобы Swift его распарсил
    stats['all_time']['favorite_drink'] = fav_drink_name
    # Добавляем дату регистрации
    reg_date = user.member_since.strftime('%Y-%m-%d') if hasattr(user,
                                                                 'member_since') and user.member_since else '2026-05-28'
    stats['all_time']['registered_at'] = reg_date

    # =========================================================================
    # 4. ИТОГОВЫЙ ОТВЕТ API
    # =========================================================================
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': getattr(user, 'email', 'user@brs.com'),
        'role': user.type if user.type else 'user',
        'monthly_badge': monthly_badge,
        'stats': stats['all_time'],  # Передаем готовую секцию 'all_time' со всеми вложенными полями
        'recent_logs': logs_data,
        'drunk_history': drunk_data
    })


@api.route('/user/favorite-bars', methods=['GET'])
def get_user_favorite_bars():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.get(3) or User.query.first()

    if not user:
        return jsonify({'bars': []}), 200

    fav_bars = user.favorite_bars.all()

    bars_json = []
    for bar in fav_bars:
        bars_json.append({
            'id': bar.id,
            'name': bar.name,
            'address': bar.address or "Адрес не указан",
            'city': bar.city or "Самара",
            'rate': float(bar.rate) if bar.rate else 0.0
        })

    return jsonify({'bars': bars_json}), 200


@api.route('/user/update-location', methods=['POST'])
def update_user_location():
    if current_user.is_authenticated:
        user = current_user
    else:
        user = User.query.get(3) or User.query.first()

    if not user:
        return jsonify({'error': 'Not Found', 'message': 'Пользователь не найден'}), 404

    json_data = request.get_json()
    if not json_data or 'city' not in json_data:
        return jsonify({'error': 'Bad Request', 'message': 'Город не указан'}), 400

    user.location = json_data.get('city').strip()
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Город успешно изменен на {user.location}',
        'current_city': user.location
    }), 200