-- Миграция 004: Очистка всех данных из БД
-- ВНИМАНИЕ: Этот скрипт удаляет ВСЕ данные из всех таблиц!
-- Используйте только если хотите полностью обнулить БД и начать заново.

-- Удаляем все данные из таблиц используя TRUNCATE CASCADE
-- CASCADE автоматически удалит данные из зависимых таблиц
-- Удаляем все таблицы одной командой - порядок не важен при использовании CASCADE
TRUNCATE TABLE 
    bids,
    moderation_queue,
    auctions,
    regular_sales,
    payments,
    products,
    users
CASCADE;

-- Сбрасываем последовательности (sequences) для автоинкрементных полей
-- Это нужно, чтобы новые записи начинались с 1, а не продолжали счетчик
ALTER SEQUENCE IF EXISTS users_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS products_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS auctions_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS regular_sales_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS bids_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS payments_id_seq RESTART WITH 1;
ALTER SEQUENCE IF EXISTS moderation_queue_id_seq RESTART WITH 1;

-- Выводим сообщение об успешной очистке
DO $$
BEGIN
    RAISE NOTICE 'Все данные успешно удалены из БД. Таблицы очищены, последовательности сброшены.';
END $$;
