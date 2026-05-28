# 📑 API Documentation: BRS

> **Статус проекта:** В разработке 🏗️
> **Базовый URL:** `http://localhost:5000/api/v1`

---

## 🧭 Навигация
- [🔐 Аутентификация](#-аутентификация)
- [👤 Пользователи (Users)](#-пользователи-users)
- [🏢 Бары (Bars)](#-бары-bars)
- [🍹 Напитки (Drinks)](#-напитки-drinks)
- [🛠 Предстоящие задачи (API Roadmap)](#-предстоящие-задачи-api-roadmap)

---

## 🔐 Аутентификация
Все защищенные методы требуют передачи токена в заголовке:
`Authorization: Bearer <your_jwt_token>`

---

## 👤 Пользователи (Users)

### `POST /auth/register`
**Статус:** ✅ Готово
Регистрация нового пользователя / эксперта.

<details>
<summary>Посмотреть детали</summary>

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "message": "User created successfully"
}
```
</details>

### `POST /auth/login`
**Статус:** ⚠️ В разработке (логика JWT готова, настраивается валидация)
Вход в систему и получение токена доступа.

<details>
<summary>Посмотреть детали</summary>

**Request Body:**
```json
{
  "email": "string",
  "password": "string"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOi...",
  "user": {
    "id": 1,
    "username": "york",
    "role": "manager"
  }
}
```
</details>

---

## 🏢 Бары (Bars)

### `GET /bars`
**Статус:** ✅ Готово (Синхронизировано с моделью `Bar.to_json()`)
Получение списка всех баров в системе.

**Query Params:**
- `limit` (int) — количество элементов на страницу (default: 10)
- `offset` (int) — смещение пагинации (default: 0)
- `distance` (int) — радиус поиска в метрах (заглушка для фильтрации)
- `rating` (float) — минимальный рейтинг заведения (например, 4.0)

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "name": "Neon & Wine",
    "address": "ул. Маросейка, 10",
    "city": "Москва",
    "rating": 4.2,
    "manager_name": "York"
  }
]
```

### `POST /bars`
**Статус:** ✅ Готово
Создание новой карточки бара администратором.

**Request Body:**
```json
{
  "name": "Craft & Draft",
  "city": "Москва",
  "address": "ул. Арбат, 22",
  "admin_id": 1
}
```

---

## 🍹 Напитки (Drinks)

### `GET /drinks`
**Статус:** ✅ Готово
Получение глобального списка абсолютно всех напитков в системе.

**Query Params:**
- `type` (string) — фильтр по категории (`Beer`, `Vodka`, `Cocktail`...)
- `score` (float) — минимальная оценка напитка

**Response (200 OK):**
```json
[
  {
    "id": 42,
    "name": "Aperol Spritz",
    "type": "Cocktail",
    "description": "Классический итальянский коктейль",
    "score": 4.5,
    "image": "image_filename.png",
    "bar_id": 1
  }
]
```
### `POST /api/v1/drinks/<int:drink_id>/rate` ЗАГЛУШКА
Authorization: Bearer <token>
Body: { "score": 5 }
Response (200 OK): { "message": "Rating updated", "new_drink_score": 4.5, "new_bar_rate": 4.2 }

### `GET /api/v1/user/profile` ЗАГЛУШКА
Authorization: Bearer <token>
Response (200 OK): 
{
  "id": 1,
  "username": "york",
  "email": "hari@k.com",
  "role": "manager",
  "stats": {
    "total_ratings_given": 42,  // сколько напитков оценил
    "favorite_bar": "Neon & Wine", // самый посещаемый бар (опционально)
    "registered_at": "2026-05-28"
  }
}

### `GET /api/v1/auth/me`
Authorization: Bearer <your_jwt_token>
Response (200 OK): { "authenticated": true, "user_id": 1, "username": "york", "role": "manager" }
Response (401 Unauthorized): { "authenticated": false, "message": "Token expired" }

### `GET /bars/<int:bar_id>/drinks`
**Статус:** 🚀 Добавлено для iOS-приложения
Получение карты напитков (меню) конкретного заведения.

**Response (200 OK):** Возвращает массив напитков, привязанных строго к указанному `bar_id`.

### `POST /bars/<int:bar_id>/drinks`
**Статус:** ✅ Готово (Синхронизировано с логикой Flask-контроллера)
Добавление нового напитка в конкретное заведение.



---

## 🛠 Предстоящие задачи (API Roadmap)
- [ ] Добавить метод для загрузки аватара пользователя (`POST /user/avatar`)
- [ ] Добавить поддержку `multipart/form-data` для загрузки изображений напитков (`POST /drinks/image`)
- [ ] Реализовать метод удаления напитка (`DELETE /drinks/<int:drink_id>`) администратором
- [ ] Настроить CORS (`Flask-CORS`) для предотвращения блокировок со стороны браузеров и внешних Swift-клиентов
