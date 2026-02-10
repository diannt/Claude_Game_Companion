# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Commands

- **Install**: `uv sync`
- **Run server**: `uv run run_server.py` (`--verbose` for debug logging)
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Pre-commit**: `pre-commit run --all-files`
- **Simulation test**: `uv run tests/simulation.py`

## Config & Secrets

- **User config**: `conf.yaml` (generated from `config_templates/conf.default.yaml` on first run)
- **Character overrides**: `characters/*.yaml`
- **Secrets**: `.env` — `QDRANT_API_KEY`, `QDRANT_CLUSTER_ENDPOINT`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`
- **Sessions**: `sessions/{user_id}/{session_id}/screenshots/` — per-user working dirs

## Architecture

### LLM Backend — WSL Claude Subprocess (sole provider)

All inference runs through `claude -p` subprocess. No API keys. No remote LLM calls.

- Implementation: `src/open_llm_vtuber/agent/stateless_llm/wsl_claude.py` → `WSLClaudeLLM`
- `WSLClaudeLLM.chat_completion()` builds a single prompt string, runs `subprocess.run(["claude", "-p", prompt], cwd=session_dir)`, parses JSON stdout, yields `text` field
- System prompt enforces JSON output: `{"text": "…[emotion]…", "emotion": "…", "action": "none"}`
- Factory (`stateless_llm_factory.py`) **always** returns `WSLClaudeLLM` regardless of `conf.yaml`
- Retry logic: 3 attempts with 1-second back-off; graceful fallback to raw output on JSON parse failure

### Conversation Pipeline

```
WebSocket → WebSocketHandler → ConversationHandler → SingleConversation
  → BasicMemoryAgent.chat() → WSLClaudeLLM.chat_completion()
  → sentence segmentation → TTSTaskManager → audio WebSocket payload → frontend
```

`BasicMemoryAgent` (`agent/agents/basic_memory_agent.py`) wraps `WSLClaudeLLM`, maintains in-memory message history, handles Live2D expression extraction from bracketed tags (e.g., `[smile]`).

### Game Knowledge — Qdrant RAG

- Module: `src/open_llm_vtuber/modules/knowledge_base.py` → `KnowledgeBase`
- Collection `game_knowledge`: 384-dim Cosine, Qdrant cloud inference via `sentence-transformers/all-minilm-l6-v2`
- `get_game_context(game_name, current_state, screenshot_path?)`:
  - Score ≥ 0.8 hit → returns `[KNOWN_TACTICS]: {tactic}`
  - Miss → runs dedicated `claude -p` research subprocess, ingests tactic + best_practices to Qdrant, returns tactic
- Context injected into system prompt via `service_context.construct_system_prompt()`

### Vision Loop — Proactive Screen Analysis

- Module: `src/open_llm_vtuber/modules/vision_loop.py` → `ScreenWatcher` (daemon thread)
- Every 15–25 s: `pyautogui.screenshot()` → save to `sessions/` → pHash comparison
- Hamming distance < 5 → AFK, skip
- On screen change: calls `knowledge_base.get_game_context()` → fires `ai-speak-signal` back through WebSocket handler

### Supabase Memory Layer

- Module: `src/open_llm_vtuber/integrations/memory_manager.py` → `MemoryManager`
- Tables: `user_history` (advice log), `chat_logs` (session dumps), `long_term_profile` (persistent preferences)
- `long_term_profile` + recent `user_history` injected into system prompt on session start
- Advice saved after each bot response; chat log saved on disconnect

### Service Context — Central DI Hub

`src/open_llm_vtuber/service_context.py` holds all engine references per session:
- `agent_engine`, `asr_engine`, `tts_engine`, `vad_engine`
- `knowledge_base` (Qdrant)
- `memory_manager` (Supabase)
- `system_prompt` — assembled by `construct_system_prompt()` which appends tool prompts, Live2D emotion map, game context, and long-term profile

### Player2 Publication Pipeline

- Specs: `docs/p2_platform_specs.md`
- Manifest generator: `src/open_llm_vtuber/publishing/generate_manifest.py` → `player2_manifest.json`
- Platform client: `src/open_llm_vtuber/publishing/player2_platform.py`

## Key Files

| Path | Role |
|------|------|
| `src/.../agent/stateless_llm/wsl_claude.py` | Only LLM provider |
| `src/.../agent/stateless_llm_factory.py` | Force-routes all LLM to wsl_claude |
| `src/.../agent/agent_factory.py` | Creates BasicMemoryAgent with wsl_claude |
| `src/.../modules/knowledge_base.py` | Qdrant RAG + research subprocess |
| `src/.../modules/vision_loop.py` | Screen watcher + proactive triggers |
| `src/.../integrations/memory_manager.py` | Supabase tables CRUD |
| `src/.../service_context.py` | DI container + system prompt assembly |
| `src/.../conversations/single_conversation.py` | Pipeline orchestration + advice saving |
| `src/.../websocket_handler.py` | WS routing, session init, vision loop start |
| `config_templates/conf.default.yaml` | Source of truth for default config |

## Adding Engines

Follow the existing factory pattern:
1. Implement interface (`asr_interface.py`, `tts_interface.py`)
2. Register in factory (`asr_factory.py`, `tts_factory.py`)
3. Add config class in `config_manager/`
4. Update `config_templates/conf.default.yaml`

**Do not add new LLM providers** — `WSLClaudeLLM` is the only permitted LLM backend.

## WebSocket Messages

To add a new message type: add to `MessageType` enum in `websocket_handler.py`, create `_handle_*` method, register in `_init_message_handlers()`.
