# Тест-план и таблица тест-кейсов проекта «Ремонтная мастерская»

## 1. Общие сведения и цель тестирования
Цель тестирования — подтвердить корректность бизнес-логики, ролевой модели доступа (RBAC), валидации входных данных, транзакционности складских списаний и целостности цепочки статусов REST API приложения «Ремонтная мастерская» (FastAPI + SQLAlchemy 2.0 + Pydantic + JWT).

## 2. Объект и область тестирования
В область автоматизированного и функционального тестирования входят:
1. **Аутентификация и авторизация** (`/api/auth/register`, `/api/auth/login`, `/api/auth/me`).
2. **Разграничение прав доступа между ролями** (`client`, `master`, `admin`), включая изоляцию заявок между клиентами и назначенными мастерами.
3. **Заявки и загрузка вложений** (`POST /api/orders`, `GET /api/orders/my`, `GET /api/orders/{id}`).
4. **Рабочее место мастера и смена статусов** (`GET /api/master/orders`, `PATCH /api/master/orders/{id}/status`, `POST /api/master/orders/{id}/comments`, `POST /api/master/orders/{id}/parts`).
5. **Складской учёт и защита от отрицательного остатка** (`/api/inventory/parts`, `/api/inventory/movements`).
6. **Панель администратора и статистика** (`/api/admin/orders`, `/api/admin/services`, `/api/admin/users`, `/api/admin/employees`, `/api/admin/stats`).

## 3. Тестовое окружение и стратегия изоляции
- **Фреймворк**: `pytest` + `fastapi.testclient.TestClient` (на базе `httpx`).
- **Тестовая БД**: отдельная изолированная файловая SQLite БД (`tmp_path / "qa_isolated.db"`) с включённым контролем внешних ключей `PRAGMA foreign_keys=ON`, подменяемая через `app.dependency_overrides[get_db]`. Рабочая PostgreSQL БД не затрагивается.
- **Файловое хранилище**: изолированный временный каталог `tmp_path / "uploads"` через `monkeypatch.setattr(settings, "upload_dir", ...)`.
- **Файл автотестов**: [tests/test_qa_suite.py](file:///c:/Users/workb/Documents/project1/tests/test_qa_suite.py) (в дополнение к модульным тестам `tests/test_*.py`).

## 4. Критерии входа и выхода
- **Критерии входа**: развёрнуты зависимости из `requirements.txt`, применена актуальная схема моделей SQLAlchemy, линтер `ruff` и проверка типов `mypy` не содержат ошибок.
- **Критерии выхода**: 100% тест-кейсов из таблицы ниже имеют статус `PASS`, отсутствует падение существующих регрессионных тестов.

---

## 5. Таблица тест-кейсов

| ID | Раздел | Шаги воспроизведения | Ожидаемый результат | Фактический результат | Статус |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Регистрация и вход | 1. Отправить `POST /api/auth/register` с валидными данными и полем `"role": "admin"`.<br>2. Отправить `POST /api/auth/login` с теми же `email` и `password`.<br>3. Вызвать `GET /api/auth/me` с полученным Bearer-токеном. | 1. Статус `201`, в ответе `role == "client"`, `password_hash` отсутствует.<br>2. Статус `200`, возвращён JWT `access_token`.<br>3. Статус `200`, возвращён профиль созданного пользователя. | Статусы `201` (`role == "client"`), `200` (выдан JWT), `200` (`email == "ivan.qa@example.ru"`). Автотест `test_tc01_tc02_register_login_and_duplicate_checks`. | **PASS** |
| **TC-02** | Регистрация (дубликаты) | 1. Повторно отправить `POST /api/auth/register` с уже занятым `email`.<br>2. Отправить `POST /api/auth/register` с новым `email`, но занятым `phone`. | В обоих случаях статус `409 Conflict` и понятное сообщение на русском о занятом e-mail / телефоне. | Получен `409 Conflict` для обоих запросов с русскоязычным `detail`. | **PASS** |
| **TC-03** | Вход (ошибки) | 1. Отправить `POST /api/auth/login` с неверным паролем.<br>2. Отправить `POST /api/auth/login` с несуществующим `email`. | Статус `401 Unauthorized`, `detail`: «Неверный e-mail или пароль». | Получен `401 Unauthorized` с сообщением «Неверный e-mail или пароль». Автотест `test_tc03_tc04_login_wrong_credentials_and_blocked_user`. | **PASS** |
| **TC-04** | Вход (блокировка) | 1. Создать пользователя с `is_active = False`.<br>2. Отправить `POST /api/auth/login` с его верными учётными данными. | Статус `403 Forbidden`, `detail` указывает, что учётная запись заблокирована. | Получен `403 Forbidden` («Учётная запись пользователя заблокирована»). | **PASS** |
| **TC-05** | Доступ между ролями (изоляция клиентов) | 1. Клиент А создаёт заявку (`POST /api/orders`).<br>2. Клиент Б запрашивает `GET /api/orders/{id}` чужой заявки.<br>3. Клиент Б запрашивает `GET /api/orders/my`. | 1. Заявка создана (`201`).<br>2. Клиент Б получает `403 Forbidden` («Доступ к чужой заявке запрещён»).<br>3. Список `GET /api/orders/my` Клиента Б пуст (`[]`). | Клиент А получил `200`, Клиент Б — `403` («Доступ к чужой заявке запрещён») и `[]` в `/orders/my`. Автотест `test_tc05_tc06_tc07_tc08_role_access_and_order_isolation`. | **PASS** |
| **TC-06** | Доступ между ролями (клиент → мастер/админ) | Авторизованный `client` вызывает `GET /api/master/orders`, `GET /api/inventory/parts`, `GET /api/admin/users`, `GET /api/admin/stats`. | На все 4 эндпоинта возвращается `403 Forbidden`. | На все 4 эндпоинта получен статус `403 Forbidden`. | **PASS** |
| **TC-07** | Доступ между ролями (чужой мастер) | 1. Админ назначает заявку Мастеру 1.<br>2. Мастер 2 пытается вызвать `PATCH /api/master/orders/{id}/status` и `POST /api/master/orders/{id}/comments`.<br>3. Мастер 1 переводит статус в `diagnostics`. | Мастер 2 получает `403 Forbidden` на оба запроса; Мастер 1 получает `200 OK`. | Мастер 2 получил `403` на статус и комментарий; Мастер 1 перевёл статус с кодом `200`. | **PASS** |
| **TC-08** | Доступ без токена / битый JWT | 1. Вызвать `GET /api/orders/my` без заголовка `Authorization`.<br>2. Вызвать `GET /api/auth/me` с заголовком `Bearer broken.jwt.token`. | В обоих случаях возвращается `401 Unauthorized`. | Получен `401 Unauthorized` для обоих запросов. | **PASS** |
| **TC-09** | Граничные значения (пустые поля) | 1. `POST /api/auth/register` с пробелами и пустыми строками.<br>2. `POST /api/orders` с `device_type="   "`, `problem_description="   "`. | Статус `422 Unprocessable Content`, валидация Pydantic отклоняет пустые значения. | Получен `422 Unprocessable Content` на обоих запросах. Автотест `test_tc09_tc10_boundary_empty_and_too_long_fields`. | **PASS** |
| **TC-10** | Граничные значения (слишком длинный текст) | 1. Регистрация с `full_name` длиной 121 символ (лимит 120).<br>2. Заявка с `device_type` (81, лимит 80), `device_brand` (81), `device_model` (121, лимит 120).<br>3. Смена статуса с `note` длиной 256 символов (лимит 255). | На все 3 запроса возвращается `422 Unprocessable Content`. | Все 3 запроса отклонены со статусом `422 Unprocessable Content`. | **PASS** |
| **TC-11** | Граничные значения (файл 0 байт) | Отправить `POST /api/orders` с вложением `empty.jpg` размером `0 байт`. | Статус `400 Bad Request`, `detail`: «Загруженный файл пуст». | Получен `400 Bad Request` («Загруженный файл пуст»). Автотест `test_tc11_tc12_tc13_boundary_photo_uploads`. | **PASS** |
| **TC-12** | Граничные значения (файл > 5 МБ) | Отправить `POST /api/orders` с вложением `huge.jpg` размером `5 МБ + 2 байта`. | Статус `400 Bad Request`, `detail`: «Размер каждой фотографии не должен превышать 5 МБ». | Получен `400 Bad Request` с сообщением о лимите 5 МБ. | **PASS** |
| **TC-13** | Граничные значения (формат и > 5 фото) | 1. Загрузить файл `script.txt` (`text/plain`).<br>2. Загрузить 6 валидных PNG-файлов в одной заявке. | 1. `400 Bad Request` («Допустимы только изображения форматов JPG, PNG или WEBP»).<br>2. `400 Bad Request` («Можно загрузить не более 5 фотографий...»). | Оба запроса отклонены с `400 Bad Request` и ожидаемыми сообщениями. | **PASS** |
| **TC-14** | Граничные значения (списание > остатка в заявке) | 1. Создать запчасть с `stock_qty = 2`.<br>2. Вызвать `POST /api/master/orders/{id}/parts` с `labor_cost = 1800` и списанием `quantity = 3`.<br>3. Проверить состояние запчасти и заявки в БД. | Статус `400 Bad Request` («Недостаточно запчасти...»). Транзакция откатывается: `stock_qty == 2`, `labor_cost == 0.00`. | Получен `400 Bad Request`, в БД `stock_qty == 2` и `labor_cost == 0.00`. Автотест `test_tc14_tc15_boundary_inventory_overdraft_and_rollback`. | **PASS** |
| **TC-15** | Граничные значения (расход > остатка на складе) | Вызвать `POST /api/inventory/movements` с `movement_type = "out"`, `quantity = 10` при `stock_qty = 2`. | Статус `400 Bad Request`, запрет отрицательного остатка; `stock_qty` остаётся `2`. | Получен `400 Bad Request`, остаток остался `2`. | **PASS** |
| **TC-16** | Граничные значения (обход цепочки статусов) | 1. Перевести заявку из `accepted` сразу в `ready`.<br>2. Перевести `accepted` → `diagnostics`.<br>3. Попытаться откатить `diagnostics` → `accepted`.<br>4. Проверить `status_history`. | 1. `400 Bad Request` («Недопустимый переход статуса...»).<br>2. `200 OK`.<br>3. `400 Bad Request`.<br>4. В истории ровно 2 записи (`accepted`, `diagnostics`). | Перескок и откат отклонены с `400 Bad Request`, в `status_history` ровно 2 записи. Автотест `test_tc16_boundary_status_transition_bypass`. | **PASS** |
