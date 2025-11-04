-- Database optimization script for <100ms response times
-- Run this to optimize PostgreSQL for high-performance API usage

-- Connection pooling optimization
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';

-- Query performance optimization
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET seq_page_cost = 1.0;
ALTER SYSTEM SET cpu_tuple_cost = 0.01;
ALTER SYSTEM SET cpu_index_tuple_cost = 0.005;
ALTER SYSTEM SET cpu_operator_cost = 0.0025;

-- Connection and timeout settings
ALTER SYSTEM SET statement_timeout = '30s';
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';
ALTER SYSTEM SET lock_timeout = '10s';

-- Logging for performance monitoring
ALTER SYSTEM SET log_min_duration_statement = 100; -- Log queries > 100ms
ALTER SYSTEM SET log_checkpoints = on;
ALTER SYSTEM SET log_connections = off; -- Disable for performance
ALTER SYSTEM SET log_disconnections = off;

-- Create indexes for fast lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_key ON api_keys(key_hash);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_timestamp ON api_requests(created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_requests_user ON api_requests(user_id, created_at);

-- Partial indexes for common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_recent_active
ON users(last_login)
WHERE is_active = true AND last_login > (CURRENT_DATE - INTERVAL '30 days');

-- Create materialized view for frequently accessed data
CREATE MATERIALIZED VIEW IF NOT EXISTS user_stats AS
SELECT
    u.id,
    u.email,
    u.created_at,
    COUNT(ar.id) as total_requests,
    MAX(ar.created_at) as last_request,
    AVG(ar.response_time_ms) as avg_response_time
FROM users u
LEFT JOIN api_requests ar ON u.id = ar.user_id
WHERE u.is_active = true
GROUP BY u.id, u.email, u.created_at;

-- Index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_stats_id ON user_stats(id);

-- Create function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_user_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY user_stats;
END;
$$ LANGUAGE plpgsql;

-- Auto-refresh every 5 minutes (run this separately as a cron job)
-- SELECT cron.schedule('refresh-user-stats', '*/5 * * * *', 'SELECT refresh_user_stats();');

-- Analyze tables for query planner
ANALYZE users;
ANALYZE api_keys;
ANALYZE api_requests;

-- Reload configuration
SELECT pg_reload_conf();