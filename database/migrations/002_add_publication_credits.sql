-- Миграция 002: Добавление счётчика оплаченных публикаций пользователям

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS publication_credits INTEGER NOT NULL DEFAULT 0;
