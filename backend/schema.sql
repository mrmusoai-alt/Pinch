-- Pinch: схема базы данных (PostgreSQL)

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    telegram_id   BIGINT UNIQUE NOT NULL,
    base_currency CHAR(3) NOT NULL DEFAULT 'RUB',
    monthly_limit NUMERIC(14, 2),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS tz_offset SMALLINT NOT NULL DEFAULT 5;
ALTER TABLE users ADD COLUMN IF NOT EXISTS remind_time TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_report BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_remind DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_report DATE;

CREATE TABLE IF NOT EXISTS categories (
    id    SMALLSERIAL PRIMARY KEY,
    slug  TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    icon  TEXT
);

INSERT INTO categories (slug, title, icon) VALUES
    ('food',      'Еда',         '🍽'),
    ('transport', 'Транспорт',   '🚕'),
    ('home',      'Дом',         '🏠'),
    ('fun',       'Развлечения', '🎮'),
    ('health',    'Здоровье',    '💊'),
    ('other',     'Другое',      '📦'),
    ('salary',    'Зарплата',    '💰')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS transactions (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('expense', 'income')),
    amount      NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    currency    CHAR(3) NOT NULL,
    category_id SMALLINT REFERENCES categories(id),
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tx_user_date
    ON transactions (user_id, created_at DESC);
