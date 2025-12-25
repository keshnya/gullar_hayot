-- Миграция 005: Добавление поля expires_at в regular_sales для отслеживания времени истечения продажи

ALTER TABLE regular_sales 
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Индекс для быстрого поиска истекших продаж
CREATE INDEX IF NOT EXISTS idx_regular_sales_expires_at ON regular_sales(expires_at) WHERE expires_at IS NOT NULL;

