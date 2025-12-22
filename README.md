# Kelyanmedia Auction Bot

Проект аукциона цветов и подарков в Telegram с интеграцией платежных систем Payme и Click.

## Структура проекта

```
kelyanmedia_notion/
├── bot/                    # Telegram бот
│   ├── handlers/          # Обработчики команд и сообщений
│   ├── keyboards/         # Клавиатуры бота
│   ├── middlewares/       # Middleware для бота
│   └── main.py            # Точка входа бота
├── database/              # Работа с БД
│   ├── models/           # SQLAlchemy модели
│   ├── migrations/       # SQL скрипты миграций
│   └── connection.py     # Подключение к БД
├── api/                   # FastAPI приложение
│   ├── routers/          # Роутеры API
│   └── main.py           # Точка входа API
├── services/              # Бизнес-логика
│   ├── auction.py        # Логика аукционов
│   ├── user.py           # Работа с пользователями
│   ├── moderation.py     # Модерация товаров
│   └── scheduler.py      # Планировщик задач
├── config.py             # Конфигурация
├── .env                  # Переменные окружения
├── .env.example          # Пример переменных
├── pyproject.toml        # Poetry конфигурация
└── requirements.txt      # Зависимости
```

## Установка

1. Установите зависимости через Poetry:
```bash
poetry install
```

Или через pip:
```bash
pip install -r requirements.txt
```

2. Создайте базу данных PostgreSQL:
```sql
CREATE DATABASE kelyanmedia_auction;
```

3. Запустите миграцию:
```bash
psql -U postgres -d kelyanmedia_auction -f database/migrations/001_create_tables.sql
```

4. Настройте `.env` файл на основе `.env.example`:
- `BOT_TOKEN` - токен Telegram бота
- `CHANNEL_ID` - ID канала для публикации товаров
- `ADMIN_USER_IDS` - ID администраторов через запятую
- Настройки базы данных
- Настройки платежных систем (пока не используются)

## Запуск

### Telegram бот
```bash
python -m bot.main
```

### FastAPI админка
```bash
python -m api.main
```

Или через uvicorn:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Админка будет доступна по адресу: http://localhost:8000/docs

## Основные функции

### Telegram бот
- Регистрация пользователей
- Выбор типа публикации (аукцион/обычная продажа)
- Пополнение баланса
- Участие в аукционах (ставки)
- Модерация товаров (для админов)

### FastAPI админка
- Статистика пользователей и продавцов
- Статистика платежей по дням/неделям
- Просмотр товаров на модерации

## TODO

- [ ] Интеграция платежных систем Payme/Click
- [ ] Web интерфейс для публикации товаров
- [ ] Публикация товаров в Telegram канал
- [ ] Уведомления о новых ставках
- [ ] Уведомления победителям аукционов
- [ ] Загрузка фото и видео для товаров

## Технологии

- Python 3.11
- aiogram 3.x (асинхронный Telegram бот)
- FastAPI (API для админки)
- SQLAlchemy async (работа с БД)
- PostgreSQL (база данных)
- Poetry (управление зависимостями)

