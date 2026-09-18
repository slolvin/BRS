from flask import Blueprint

main = Blueprint("main", __name__)

# Импорты в самом конце для предотвращения циклических зависимостей
from . import errors, views
