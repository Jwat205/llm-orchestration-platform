-- Create additional databases for testing
CREATE DATABASE llm_api_test;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE llm_api TO postgres;
GRANT ALL PRIVILEGES ON DATABASE llm_api_test TO postgres;
