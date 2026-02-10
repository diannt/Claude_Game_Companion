-- Phase 4: Supabase memory tables
-- Run this once in the Supabase SQL editor: https://supabase.com/dashboard/project/krldbicmxgfqqrgdlwcq/sql

CREATE TABLE IF NOT EXISTS user_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    game_name TEXT,
    advice_given TEXT,
    user_reaction TEXT DEFAULT 'unknown',
    session_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    session_id TEXT,
    chat_history JSONB,
    chat_summary TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS long_term_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    bot_id TEXT DEFAULT 'mao_pro',
    preferences_json JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, bot_id)
);
