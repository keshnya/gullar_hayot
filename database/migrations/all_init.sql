-- Полная инициализация схемы БД для продакшена
-- Объединяет 001_create_tables.sql, 002_add_moderator_field.sql,
-- 002_add_publication_credits.sql и 003_add_payment_metadata.sql

-- ============================
-- 001_create_tables.sql
-- ============================

-- Миграция 001: Создание всех таблиц

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    phone VARCHAR(20),
    contact_info VARCHAR(500),
    balance INTEGER DEFAULT 0 NOT NULL,
    is_seller BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Индексы для users
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_is_seller ON users(is_seller);

-- Таблица товаров
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    product_type VARCHAR(50) NOT NULL CHECK (product_type IN ('flowers', 'gift', 'other')),
    description TEXT,
    photos TEXT,  -- JSON массив путей к фото
    video VARCHAR(500),
    price INTEGER NOT NULL,
    contact_info VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Индексы для products
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_product_type ON products(product_type);
CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active);

-- Таблица аукционов
CREATE TABLE IF NOT EXISTS auctions (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT UNIQUE NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    start_price INTEGER NOT NULL,
    current_price INTEGER NOT NULL,
    winner_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'active', 'finished', 'cancelled')),
    started_at TIMESTAMP WITH TIME ZONE,
    ends_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    channel_message_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Индексы для auctions
CREATE INDEX IF NOT EXISTS idx_auctions_product_id ON auctions(product_id);
CREATE INDEX IF NOT EXISTS idx_auctions_status ON auctions(status);
CREATE INDEX IF NOT EXISTS idx_auctions_ends_at ON auctions(ends_at);
CREATE INDEX IF NOT EXISTS idx_auctions_winner_id ON auctions(winner_id);

-- Таблица обычных продаж
CREATE TABLE IF NOT EXISTS regular_sales (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT UNIQUE NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price INTEGER NOT NULL,
    buyer_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'active', 'sold', 'cancelled')),
    channel_message_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    sold_at TIMESTAMP WITH TIME ZONE
);

-- Индексы для regular_sales
CREATE INDEX IF NOT EXISTS idx_regular_sales_product_id ON regular_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_regular_sales_status ON regular_sales(status);
CREATE INDEX IF NOT EXISTS idx_regular_sales_buyer_id ON regular_sales(buyer_id);

-- Таблица ставок
CREATE TABLE IF NOT EXISTS bids (
    id BIGSERIAL PRIMARY KEY,
    auction_id BIGINT NOT NULL REFERENCES auctions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    is_winning BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Индексы для bids
CREATE INDEX IF NOT EXISTS idx_bids_auction_id ON bids(auction_id);
CREATE INDEX IF NOT EXISTS idx_bids_user_id ON bids(user_id);
CREATE INDEX IF NOT EXISTS idx_bids_created_at ON bids(created_at);
CREATE INDEX IF NOT EXISTS idx_bids_auction_created ON bids(auction_id, created_at DESC);

-- Таблица платежей
CREATE TABLE IF NOT EXISTS payments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    payment_type VARCHAR(50) NOT NULL CHECK (payment_type IN ('balance_topup', 'publication')),
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('payme', 'click')),
    status VARCHAR(50) DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'cancelled')),
    transaction_id VARCHAR(255) UNIQUE,
    external_id VARCHAR(255),
    payment_metadata VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Индексы для payments
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_payment_type ON payments(payment_type);
CREATE INDEX IF NOT EXISTS idx_payments_transaction_id ON payments(transaction_id);
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);

-- Таблица очереди модерации
CREATE TABLE IF NOT EXISTS moderation_queue (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT UNIQUE NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
    moderator_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    moderated_at TIMESTAMP WITH TIME ZONE
);

-- Индексы для moderation_queue
CREATE INDEX IF NOT EXISTS idx_moderation_queue_product_id ON moderation_queue(product_id);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_user_id ON moderation_queue(user_id);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_status ON moderation_queue(status);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_created_at ON moderation_queue(created_at);


-- ============================
-- 002_add_moderator_field.sql
-- ============================

-- Миграция 002: Добавление поля is_moderator в таблицу users

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_moderator BOOLEAN DEFAULT FALSE NOT NULL;

-- Индекс для быстрого поиска модераторов
CREATE INDEX IF NOT EXISTS idx_users_is_moderator ON users(is_moderator);


-- ====================================
-- 002_add_publication_credits.sql
-- ====================================

-- Миграция 002: Добавление счётчика оплаченных публикаций пользователям

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS publication_credits INTEGER NOT NULL DEFAULT 0;


-- ============================
-- 003_add_payment_metadata.sql
-- ============================

-- Миграция 003: Добавление столбца payment_metadata в таблицу payments
ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS payment_metadata VARCHAR(1000);


