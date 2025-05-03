-- Create the database if it doesn't exist
SELECT 'CREATE DATABASE webhooks'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'webhooks');

-- Connect to the webhooks database
\c webhooks

-- Create the schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS public;

-- Grant necessary permissions
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public; 