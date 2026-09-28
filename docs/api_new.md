# 📑 API Documentation: BRS (Beer Rating System)

> **Статус проекта:** Готов к деплою 🚀
> **Базовый URL в Docker/Проде:** `http://localhost/api/v1.0` (или `https://yourdomain.com`)
> **Формат данных:** `application/json` (если не указано иное)

---

## 🧭 Навигация
- [🔐 Аутентификация и Доступы](#-аутентификация-и-доступы)
- [👤 Управление профилем (User Profile)](#-управление-профилем-user-profile)
- [🏢 Карты и Заведения (Bars)](#-карты-и-заведения-bars)
- [🍹 Каталог напитков (Drinks)](#-каталог-напитков-drinks)
- [📈 Журнал и Статистика (Metrics & Logs)](#-журнал-и-статистика-metrics--logs)

---

## 🔐 Аутентификация и Доступы

Все защищенные методы требуют передачи токена доступа, сгенерированного бэкендом на основе вашего `SECRET_KEY` по алгоритму **HS256**:
`Authorization: Bearer <your_jwt_token>`

### Ролевая модель системы (RBAC)
*   `user` — Просмотр карты, лог напитков, оценки, чекины по QR, удаление своего профиля.
*   `manager` — Всё, что доступно пользователю + добавление и редактирование напитков (`Add Drink`, `PUT /drinks`).
*   `administrator` — Полный доступ ко всем ресурсам системы, включая создание заведений (`Add Bar`) и управление правами пользователей.

---

## 👤 Управление профилем (User Profile)

### `POST /auth/register`
**Статус:** ✅ Готово  
Регистрация нового аккаунта в системе.

<details>
<summary>Посмотреть спецификацию</summary>

**Request Body:**
```json
{
  "username": "slava_user",
  "email": "slava@brs.app",
  "password": "my_secure_password"
}
```

**Response (201 Created):**
```json
{
  "id": 16,
  "message": "User created successfully"
}
```
</details>

### `POST /auth/login`
**Статус:** ✅ Готово  
Авторизация пользователя и генерация долгосрочного JWT-токена (срок действия — 7 дней).

<details>
<summary>Посмотреть спецификацию</summary>

**Request Body:**
```json
{
  "email": "slava@brs.app",
  "password": "my_secure_password"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 16,
    "username": "slava_user",
    "role": "user"
  }
}
```
</details>

### `GET /auth/me`
**Статус:** ✅ Готово  
Быстрая проверка валидности токена при старте Swift-приложения.

<details>
<summary>Посмотреть спецификацию</summary>

**Response (200 OK):**
```json
{
  "authenticated": true,
  "user_id": 16,
  "username": "slava_user",
  "role": "user"
}
```

**Response (401 Unauthorized):**
```json
{
  "authenticated": false,
  "message": "Token expired or invalid"
}
```
</details>

### `GET /user/profile`
**Статус:** ✅ Синхронизировано со Swift  
Получение метаданных текущего профиля для бокового меню и экрана статистики.

<details>
<summary>Посмотреть спецификацию</summary>

**Response (200 OK):**
```json
{
  "id": 16,
  "username": "slava_user",
  "email": "slava@brs.app",
  "role": "user",
  "stats": {
    "total_ratings_given": 42,
    "favorite_bar": "На Дне",
    "registered_at": "2026-09-28T19:52:34"
  }
}
```
</details>

### `DELETE /user/delete-account`
**Статус:** 🔥 Критическое требование Apple  
Полное безвозвратное стирание аккаунта. Метод автоматически запускает **каскадное удаление данных на уровне СУБД PostgreSQL**, очищая таблицы чекинов `bar_checkins`, логи `action_logs` и историю выпитого.

<details>
<summary>Посмотреть спецификацию</summary>

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Аккаунт и все связанные метрики, включая чекины, успешно стерты из системы BRS"
}
```

**Response (401 Unauthorized):**
```json
{
  "status": "error",
  "message": "Невалидный или истекший токен"
}
```
</details>

---

## 🏢 Карты и Заведения (Bars)

### `GET /bars/map`
**Статус:** 🚀 Оптимизировано для карт Leaflet и Swift  
Получение списка гео-маркеров баров для отображения на карте. Автоматически принимает город, экранируя кириллические символы.

**Query Params:**
- `city` (string) — Название текущего города поиска (default: `Любляна`)

<details>
<summary>Посмотреть спецификацию</summary>

**Response (200 OK):**
```json
{
  "city": "Любляна",
  "bars": [
    {
      "id": 1,
      "name": "Loo-Blah-Nah Craft Bar",
      "latitude": 46.0569,
      "longitude": 14.5058,
      "rating": 4.8
    }
  ]
}
```
</details>

### `GET /bars`
**Статус:** ✅ Готово  
Получение расширенного списка заведений с пагинацией и фильтрами.

**Query Params:**
- `limit` (int) — лимит элементов на страницу (default: 10)
- `offset` (int) — смещение пагинации (default: 0)
- `rating` (float) — минимальный порог рейтинга заведения (например, 4.0)

<details>
<summary>Посмотреть спецификацию</summary>

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
</details>

### `POST /bars`
**Статус:** 🔐 Доступ: `administrator`  
Создание новой карточки бара в глобальной системе.

<details>
<summary>Посмотреть спецификацию</summary>

**Request Body:**
```json
{
  "name": "Craft & Draft",
  "city": "Самара",
  "address": "ул. Арбат, 22"
}
```

**Response (201 Created):**
```json
{
  "id": 3,
  "message": "Bar created successfully"
}
```
</details>

---

## 🍹 Каталог напитков (Drinks)

### `GET /drinks`
**Статус:** ✅ Готово  
Получение глобального списка абсолютно всех напитков в системе.

**Query Params:**
- `type` (string) — фильтр по категории (`Beer`, `Cocktail`, `Wine`)
- `score` (float) — минимальная средняя оценка

<details>
<summary>Посмотреть спецификацию</summary>

**Response (200 OK):**
```json
[
  {
    "id": 42,
    "name": "Aperol Spritz",
    "type": "Cocktail",
    "description": "Классический итальянский коктейль",
    "score": 4.5,
    "image": "aperol.png",
    "bar_id": 1
  }
]
```
</details>

### `GET /bars/<int:bar_id>/drinks`
**Статус:** 🚀 Оптимизировано для iOS  
Получение карты напитков (меню) конкретного выбранного заведения.

**Response (200 OK):** Массив объектов `Drink`, привязанных строго к указанному `bar_id`.

### `POST /bars/<int:bar_id>/drinks`
**Статус:** 🔐 Доступ: `manager` или `administrator`  
Привязка и создание нового напитка в меню конкретного заведения.

### `PUT /drinks/<int:drink_id>`
**Статус:** 🔐 Доступ: `manager` | Автоматическая очистка Docker-хранилища  
Полное или частичное редактирование напитка. При загрузке новой картинки бэкенд автоматически удаляет старый файл из каталога СУБД, спасая диск сервера от мусора.

**Content-Type:** `multipart/form-data`

**Request Body:**
- `name` (string) — название
- `type` (string) — категория
- `description` (string) — описание
- `image` (file, optional) — новый медиафайл взамен старого

<details>
<summary>Посмотреть спецификацию</summary>

**Response (200 OK):**
```json
{
  "id": 42,
  "message": "The drink has been updated.",
  "image_path": "new_photo_2026.jpg"
}
```
</details>

### `DELETE /drinks/<int:drink_id>`
**Статус:** 🔐 Доступ: `administrator`  
Полное физическое удаление напитка и каскадное стирание файла его изображения из локальной папки `static/drinks/`.

**Response (200 OK):**
```json
{
  "id": 42,
  "message": "Drink and its image file deleted successfully."
}
```

---

## 📈 Журнал и Статистика (Metrics & Logs)

### `POST /drinks/<int:drink_id>/rate`
**Статус:** ✅ Готово (Интегрировано с логами действий)  
Выставление оценки напитку пользователем. Автоматически пересчитывает средний балл напитка и глобальный рейтинг самого бара.

<details>
<summary>Посмотреть спецификацию</summary>

**Request Body:**
```json
{ 
  "score": 5 
}
```

**Response (200 OK):**
```json
{ 
  "message": "Rating updated", 
  "new_drink_score": 4.7, 
  "new_bar_rate": 4.5 
}
```
</details>

### `GET /privacy`
**Статус:** 🌐 Интеллектуальный роут для Apple  
Страница политики конфиденциальности. На основе системного `User-Agent` определяет устройство: вебу отдает полную стильную версию, а для iOS WebView — чистый отцентрованный минималистичный текст.

---

## 🛠 Предстоящие задачи (API Roadmap)
- [ ] Реализовать метод загрузки персонального аватара пользователя (`POST /user/avatar`)
- [x] Внедрить поддержку `multipart/form-data` для безопасной работы с изображениями в Docker.
- [x] Добавить каскадные ограничения внешних ключей `ondelete="CASCADE"` в СУБД Postgres.
- [ ] Подключить пакет `Flask-CORS` для защиты от кросс-доменных блокировок веб-запросов со стороны сторонних клиентов.
