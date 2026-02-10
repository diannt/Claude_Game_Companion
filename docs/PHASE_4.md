# Phase 4: Supabase Memory Layer

## Start: 2026-02-10T10:47:40Z

## Scope
- `src/open_llm_vtuber/integrations/memory_manager.py` — Supabase CRUD
- `src/open_llm_vtuber/service_context.py` — MemoryManager instantiation + profile injection
- `src/open_llm_vtuber/conversations/single_conversation.py` — save advice after each response
- `src/open_llm_vtuber/websocket_handler.py` — save chat log on disconnect
- `src/open_llm_vtuber/modules/knowledge_base.py` — track `current_game_name`
- `migrations/001_create_tables.sql` — DDL for Supabase SQL editor

## Supabase Tables Created
- `user_history`: user_id, game_name, advice_given, user_reaction, session_id, timestamp
- `chat_logs`: user_id, session_id, chat_history (jsonb), chat_summary, timestamp
- `long_term_profile`: user_id, bot_id, preferences_json (jsonb), UNIQUE(user_id, bot_id)

Created via psycopg2 session-mode pooler: `aws-0-us-west-2.pooler.supabase.com:5432`

## Live Test Results (2026-02-10)

| Test | Result |
|------|--------|
| `MemoryManager` connects to Supabase | PASS |
| `save_advice()` inserts row to `user_history` | PASS |
| `get_recent_advice()` returns rows | PASS — "Roll toward Margit on the delayed overhead strike." |
| `update_profile()` upserts `long_term_profile` | PASS |
| `get_long_term_profile()` returns merged prefs | PASS — `{'preferred_game': 'Elden Ring', 'skill_level': 'intermediate'}` |
| `build_profile_prompt()` returns formatted string | PASS — `[USER PROFILE]` + `[RECENT ADVICE GIVEN]` blocks |

## Integration Points
- `service_context.construct_system_prompt()` prepends `build_profile_prompt()` output
- `single_conversation.process_single_conversation()` calls `save_advice()` after each bot response
- `websocket_handler.handle_disconnect()` calls `save_chat_log()` with full session history
- `KnowledgeBase.current_game_name` tracked and passed to `save_advice()`

## End: 2026-02-10T04:30:00Z
