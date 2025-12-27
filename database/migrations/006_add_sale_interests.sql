-- Миграция: создание таблицы для отслеживания интересов покупателей
-- Один покупатель может нажать "Хочу купить" только 1 раз на каждое объявление

CREATE TABLE IF NOT EXISTS sale_interests (
    id BIGSERIAL PRIMARY KEY,
    sale_id BIGINT NOT NULL REFERENCES regular_sales(id) ON DELETE CASCADE,
    buyer_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Уникальное ограничение: один покупатель - одна продажа
    CONSTRAINT uq_sale_buyer UNIQUE (sale_id, buyer_id)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_sale_interests_sale_id ON sale_interests(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_interests_buyer_id ON sale_interests(buyer_id);

