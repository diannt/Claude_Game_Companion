# Phase 4: Supabase Memory Layer + Player2 Platform

## Start: 2026-02-10T10:47:40Z

## Scope
- `src/open_llm_vtuber/integrations/__init__.py`
- `src/open_llm_vtuber/integrations/memory_manager.py` — Supabase tables
- `src/open_llm_vtuber/service_context.py` — integrate MemoryManager
- `src/open_llm_vtuber/conversations/single_conversation.py` — save advice + chat logs
- `docs/p2_platform_specs.md` — Player2 research
- `src/open_llm_vtuber/publishing/player2_platform.py` — publishing client
- `src/open_llm_vtuber/publishing/generate_manifest.py` — manifest generator
- `player2_manifest.json` — output manifest

## Supabase Tables
- `user_history`: user_id, game_name, advice_given, user_reaction, timestamp
- `chat_logs`: user_id, chat_history (jsonb), chat_summary, session_id, timestamp
- `long_term_profile`: user_id, bot_id, preferences_json (jsonb)

## Tests
- [ ] MemoryManager connects to Supabase
- [ ] user_history row inserted after advice
- [ ] chat_logs saved on session end
- [ ] long_term_profile fetched and injected into system prompt
- [ ] player2_manifest.json generated

## End: TBD
