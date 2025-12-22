-- Миграция 002: Добавление поля is_moderator в таблицу users

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_moderator BOOLEAN DEFAULT FALSE NOT NULL;

-- Индекс для быстрого поиска модераторов
CREATE INDEX IF NOT EXISTS idx_users_is_moderator ON users(is_moderator);

