# Инструкция по настройке проекта

## Шаг 1: Установка зависимостей

### Через Poetry (рекомендуется):
```bash
poetry install
```

### Через pip:
```bash
pip install -r requirements.txt
```

## Шаг 2: Настройка базы данных

1. Убедитесь, что PostgreSQL запущен локально

2. Создайте базу данных:
```sql
CREATE DATABASE kelyanmedia_auction;
```

3. Запустите миграцию:
```bash
psql -U postgres -d kelyanmedia_auction -f database/migrations/001_create_tables.sql
```

Или через psql:
```bash
psql -U postgres
\c kelyanmedia_auction
\i database/migrations/001_create_tables.sql
```

## Шаг 3: Настройка переменных окружения

1. Скопируйте `.env.example` в `.env`:
```bash
cp .env.example .env
```

2. Отредактируйте `.env` и укажите:
   - `BOT_TOKEN` - токен вашего Telegram бота (получить у @BotFather)
   - `CHANNEL_ID` - ID канала для публикации товаров (формат: `-1001234567890`)
   - `ADMIN_USER_IDS` - ID администраторов через запятую (например: `123456789,987654321`)
   - Настройки базы данных (если отличаются от стандартных)

## Шаг 4: Запуск приложений

### Запуск Telegram бота:
```bash
python run_bot.py
```

Или:
```bash
python -m bot.main
```

### Запуск FastAPI админки (в отдельном терминале):
```bash
python run_api.py
```

Или:
```bash
python -m api.main
```

Админка будет доступна по адресу: http://localhost:8000/docs

## Проверка работы

1. Запустите бота и отправьте команду `/start` в Telegram
2. Откройте http://localhost:8000/docs и проверьте доступность API
3. Проверьте статистику через `/api/admin/stats`

## Примечания

- Бот и API можно запускать параллельно в разных терминалах
- Платежные системы (Payme/Click) пока не интегрированы - это будет сделано позже
- Web интерфейс для публикации товаров также будет добавлен позже
- Для работы модерации нужно указать ID администраторов в `ADMIN_USER_IDS`

