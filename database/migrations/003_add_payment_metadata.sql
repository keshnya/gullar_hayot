-- Миграция 003: Добавление столбца payment_metadata в таблицу payments

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS payment_metadata VARCHAR(1000);
