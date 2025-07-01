-- Отключение Row Level Security для таблиц бота
-- Выполни этот SQL в Supabase Dashboard -> SQL Editor

-- Отключаем RLS для всех таблиц
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions DISABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_limits DISABLE ROW LEVEL SECURITY;
ALTER TABLE usage_log DISABLE ROW LEVEL SECURITY;
ALTER TABLE payments DISABLE ROW LEVEL SECURITY;

-- Или альтернативно - создать политики для anon роли
-- Раскомментируй если хочешь оставить RLS включенным:

/*
-- Включаем RLS (если отключен)
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE subscription_limits ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE usage_log ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- Создаем политики для anon роли (публичный API ключ)
CREATE POLICY "Allow all operations for anon" ON users FOR ALL TO anon USING (true);
CREATE POLICY "Allow all operations for anon" ON subscriptions FOR ALL TO anon USING (true);
CREATE POLICY "Allow all operations for anon" ON subscription_limits FOR ALL TO anon USING (true);
CREATE POLICY "Allow all operations for anon" ON usage_log FOR ALL TO anon USING (true);
CREATE POLICY "Allow all operations for anon" ON payments FOR ALL TO anon USING (true);
*/ 