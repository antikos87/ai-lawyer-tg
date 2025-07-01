-- Схема базы данных для AI-Юрист подписок
-- Supabase PostgreSQL Schema

-- Таблица пользователей
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    current_subscription_id UUID REFERENCES subscriptions(id),
    trial_used BOOLEAN DEFAULT FALSE,
    trial_started_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Типы подписок
CREATE TYPE subscription_type AS ENUM ('trial', 'basic', 'premium', 'corporate');

-- Статусы подписок
CREATE TYPE subscription_status AS ENUM ('active', 'expired', 'cancelled', 'pending');

-- Таблица подписок
CREATE TABLE subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type subscription_type NOT NULL,
    status subscription_status NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    auto_renewal BOOLEAN DEFAULT TRUE,
    payment_id TEXT, -- YooKassa payment ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Лимиты по тарифам
CREATE TABLE subscription_limits (
    subscription_type subscription_type PRIMARY KEY,
    consultations_limit INTEGER,
    documents_limit INTEGER,
    analysis_limit INTEGER,
    price_kopecks INTEGER NOT NULL, -- цена в копейках
    duration_days INTEGER NOT NULL
);

-- Заполняем лимиты
INSERT INTO subscription_limits VALUES
('trial', 3, 2, 1, 0, 1),
('basic', 25, 10, 5, 79000, 30),
('premium', -1, 30, 15, 149000, 30), -- -1 = безлимит
('corporate', -1, 100, 50, 399000, 30);

-- Таблица использования
CREATE TABLE usage_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id),
    action_type TEXT NOT NULL, -- 'consultation', 'document', 'analysis'
    details JSONB, -- дополнительная информация
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица платежей
CREATE TABLE payments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id),
    yookassa_payment_id TEXT UNIQUE NOT NULL,
    amount_kopecks INTEGER NOT NULL,
    status TEXT NOT NULL, -- 'pending', 'succeeded', 'cancelled'
    payment_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для производительности
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_usage_logs_user_id ON usage_logs(user_id);
CREATE INDEX idx_usage_logs_created_at ON usage_logs(created_at);
CREATE INDEX idx_payments_yookassa_id ON payments(yookassa_payment_id);

-- RLS (Row Level Security) политики
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Функция для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггеры для автоматического обновления updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_payments_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция для получения текущего использования
CREATE OR REPLACE FUNCTION get_current_usage(p_user_id UUID, p_subscription_id UUID)
RETURNS TABLE(
    consultations_used INTEGER,
    documents_used INTEGER,
    analysis_used INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(CASE WHEN action_type = 'consultation' THEN 1 ELSE 0 END)::INTEGER, 0) as consultations_used,
        COALESCE(SUM(CASE WHEN action_type = 'document' THEN 1 ELSE 0 END)::INTEGER, 0) as documents_used,
        COALESCE(SUM(CASE WHEN action_type = 'analysis' THEN 1 ELSE 0 END)::INTEGER, 0) as analysis_used
    FROM usage_logs 
    WHERE user_id = p_user_id 
    AND subscription_id = p_subscription_id;
END;
$$ LANGUAGE plpgsql;

-- Функция для проверки лимитов
CREATE OR REPLACE FUNCTION check_limit(p_user_id UUID, p_action_type TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    current_sub RECORD;
    limits RECORD;
    usage RECORD;
BEGIN
    -- Получаем текущую подписку
    SELECT * INTO current_sub
    FROM subscriptions s
    JOIN users u ON u.current_subscription_id = s.id
    WHERE u.id = p_user_id
    AND s.status = 'active'
    AND s.expires_at > NOW();
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Получаем лимиты
    SELECT * INTO limits
    FROM subscription_limits
    WHERE subscription_type = current_sub.type;
    
    -- Получаем текущее использование
    SELECT * INTO usage
    FROM get_current_usage(p_user_id, current_sub.id);
    
    -- Проверяем лимит
    CASE p_action_type
        WHEN 'consultation' THEN
            RETURN limits.consultations_limit = -1 OR usage.consultations_used < limits.consultations_limit;
        WHEN 'document' THEN
            RETURN limits.documents_limit = -1 OR usage.documents_used < limits.documents_limit;
        WHEN 'analysis' THEN
            RETURN limits.analysis_limit = -1 OR usage.analysis_used < limits.analysis_limit;
        ELSE
            RETURN FALSE;
    END CASE;
END;
$$ LANGUAGE plpgsql; 