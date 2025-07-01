-- Создание таблиц для AI-Lawyer Telegram Bot

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    trial_used BOOLEAN DEFAULT FALSE,
    trial_started_at TIMESTAMP WITH TIME ZONE,
    current_subscription_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица подписок
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('trial', 'basic', 'premium', 'corporate')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    payment_id TEXT,
    auto_renewal BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица лимитов подписок
CREATE TABLE IF NOT EXISTS subscription_limits (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    subscription_type TEXT UNIQUE NOT NULL,
    consultations_limit INTEGER DEFAULT -1,
    documents_limit INTEGER DEFAULT -1,
    analysis_limit INTEGER DEFAULT -1,
    duration_days INTEGER NOT NULL,
    price_kopecks INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица использования
CREATE TABLE IF NOT EXISTS usage_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL CHECK (action_type IN ('consultation', 'document', 'analysis')),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица платежей
CREATE TABLE IF NOT EXISTS payments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_type TEXT NOT NULL,
    yookassa_payment_id TEXT UNIQUE NOT NULL,
    amount_kopecks INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'succeeded', 'cancelled', 'failed')),
    payment_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_usage_log_user_id ON usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_log_created_at ON usage_log(created_at);
CREATE INDEX IF NOT EXISTS idx_payments_yookassa_id ON payments(yookassa_payment_id);

-- Заполнение данными лимитов
INSERT INTO subscription_limits (subscription_type, consultations_limit, documents_limit, analysis_limit, duration_days, price_kopecks) VALUES
('trial', 3, 2, 1, 1, 0),
('basic', 25, 10, 5, 30, 79000),
('premium', -1, 30, 15, 30, 149000),
('corporate', -1, 100, 50, 30, 399000)
ON CONFLICT (subscription_type) DO NOTHING;

-- Функция для получения статистики использования текущего месяца
CREATE OR REPLACE FUNCTION get_current_usage(p_user_id UUID, p_subscription_id UUID)
RETURNS TABLE(
    consultations_used INTEGER,
    documents_used INTEGER,
    analysis_used INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(CASE WHEN action_type = 'consultation' THEN 1 ELSE 0 END), 0)::INTEGER,
        COALESCE(SUM(CASE WHEN action_type = 'document' THEN 1 ELSE 0 END), 0)::INTEGER,
        COALESCE(SUM(CASE WHEN action_type = 'analysis' THEN 1 ELSE 0 END), 0)::INTEGER
    FROM usage_log 
    WHERE user_id = p_user_id 
    AND subscription_id = p_subscription_id
    AND created_at >= DATE_TRUNC('month', NOW());
END;
$$ LANGUAGE plpgsql;

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column(); 