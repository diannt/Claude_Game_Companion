# Gameplay Companion — Self-Learning AI Coach

A real-time gameplay coaching companion built on top of Open-LLM-VTuber.
Watches your screen, identifies the game, gives specific tactical advice via a Live2D avatar,
and remembers what it has told you across sessions.

---

## What it does

1. **Watches your screen** — takes a screenshot every 15–25 s via PowerShell (WSL2 compatible)
2. **Identifies the game** — sends the screenshot to `claude -p` with `@/path/to/screenshot.png`; Claude visually identifies the game, boss, current state, and returns a tactical JSON
3. **Caches knowledge in Qdrant** — ingested tactic + best-practices vectors are reused on the next capture (no redundant research calls)
4. **Delivers advice through a Live2D avatar** — proactive `ai-speak-signal` fires if screen changed; also responds to direct voice/text questions
5. **Remembers the user** — Supabase stores every piece of advice given (`user_history`), long-term preferences (`long_term_profile`), and full session chat logs (`chat_logs`). Profile is injected into the system prompt at session start.

---

## Architecture

```
Screen (Windows display)
  ↓ PowerShell CopyFromScreen every 15–25 s
ScreenWatcher (daemon thread)  ←  pHash Hamming < 5 → skip AFK
  ↓ screenshot path
KnowledgeBase.get_game_context(@path)
  ↓ game_name == "unknown"          ↓ known game
  claude -p @screenshot             Qdrant vector search (score ≥ 0.8)
  → JSON: game, state, tactic       → HIT: return cached tactic
  → Qdrant ingest (tactic + tips)   → MISS: claude research + ingest
  → current_game_name updated
  ↓ tactic text
ai-speak-signal → WebSocketHandler → ConversationHandler
  → BasicMemoryAgent → WSLClaudeLLM (claude -p subprocess)
  → TTS → Live2D avatar speaks
  ↓
MemoryManager.save_advice(game_name, advice)  →  Supabase user_history
```

### LLM

All inference uses `claude -p` (WSL subprocess, no API keys, no remote LLM calls).
Sole provider: `WSLClaudeLLM` in `src/open_llm_vtuber/agent/stateless_llm/wsl_claude.py`.

### RAG

Qdrant cloud collection `game_knowledge` (384-dim Cosine, `sentence-transformers/all-minilm-l6-v2`).
Game-specific tactics and best-practices are ingested on first encounter and reused thereafter.

### Memory

Supabase (PostgreSQL) tables:
- `user_history` — every piece of advice given with game name + timestamp
- `chat_logs` — full session history saved on disconnect
- `long_term_profile` — persistent user preferences injected into system prompt

---

## Setup

### Prerequisites
- WSL2 with Ubuntu
- `claude` CLI installed and authenticated (`~/.local/bin/claude`)
- Qdrant cloud account
- Supabase project

### Install

```bash
uv sync
```

### Configure

Copy `.env.example` to `.env` and fill in:

```
QDRANT_API_KEY=...
QDRANT_CLUSTER_ENDPOINT=https://<id>.qdrant.io
SUPABASE_URL=https://<id>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

Create the Supabase tables using `migrations/001_create_tables.sql` in the Supabase SQL editor.

### Run

```bash
uv run run_server.py
```

Open `http://localhost:12393` in a browser. Start playing a game — the companion will begin commenting within 15–25 seconds.

---

## Key files

| File | Role |
|------|------|
| `src/.../agent/stateless_llm/wsl_claude.py` | Claude subprocess LLM (only provider) |
| `src/.../modules/knowledge_base.py` | Qdrant RAG + Claude visual research |
| `src/.../modules/vision_loop.py` | Screen watcher + proactive triggers |
| `src/.../integrations/memory_manager.py` | Supabase CRUD |
| `src/.../service_context.py` | DI container + system prompt assembly |
| `src/.../conversations/single_conversation.py` | Pipeline + advice saving |
| `src/.../websocket_handler.py` | WS routing, session init, vision loop |
| `migrations/001_create_tables.sql` | Supabase DDL |
| `docs/PHASE_*.md` | Per-phase development logs with live test results |

---

## Development

```bash
# Lint
ruff check .

# Format
ruff format .

# Run simulation test
uv run tests/simulation.py
```

See `CLAUDE.md` for full architecture notes and `PLAN.md` for the transformation roadmap.
