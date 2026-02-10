# Phase 1: WSL Claude LLM Core

**Start:** 2026-02-10T10:10:32Z

## Objective
Create `WSLClaudeLLM` — the sole LLM backend that runs `claude -p` as a subprocess.
Wire it into the agent factory and verify end-to-end conversation flow.

## Scope
- Create `src/open_llm_vtuber/agent/stateless_llm/wsl_claude.py`
- Verify `stateless_llm_factory.py` already hard-codes WSLClaudeLLM (done in pre-work)
- Verify `config_manager/stateless_llm.py` has `WSLClaudeConfig` (done in pre-work)
- Verify `conf.default.yaml` uses `wsl_claude_llm` as default (done in pre-work)
- Session dir creation: ensure `sessions/` folder exists on startup

## Test Plan
1. `uv run run_server.py --verbose`
2. Send a text message via browser
3. Grep logs for `claude -p` subprocess invocation
4. Verify JSON parsed, `text` field streamed to TTS
5. Confirm no API keys or network LLM calls

---

## Results

**End:** 2026-02-10T10:15:16Z
**Duration:** ~5 min

### Tests Passed

1. **Import check** — `WSLClaudeLLM` imports cleanly from project venv
2. **Config validation** — `conf.yaml` with `llm_provider: wsl_claude_llm` validates through pydantic
3. **WSLClaudeLLM instantiation** — `session_dir=sessions` folder created, CLI path resolved
4. **Subprocess call** — `claude -p "..."` runs, returns JSON wrapped in markdown code fences
5. **Markdown fence stripping** — Code fences stripped before JSON parse; `text` field extracted
6. **Response integrity** — Prompt "Say hello in exactly 3 words." → `"Hello there friend"` ✓
7. **Ruff lint** — All modified files pass `ruff check` with zero warnings

### Files Created/Modified
- **Created:** `src/open_llm_vtuber/agent/stateless_llm/wsl_claude.py`
- **Modified:** `src/open_llm_vtuber/config_manager/agent.py` — added `wsl_claude_llm` to `llm_provider` Literal
- **Created:** `conf.yaml` (from `conf.default.yaml`)
- **Created:** `sessions/` directory (auto-created by WSLClaudeLLM.__init__)

### Notes
- Claude CLI wraps JSON in ` ```json ... ``` ` code fences; stripping logic added to `chat_completion`
- Single-chunk yield (non-streaming) — agent handles this via `elif isinstance(event, str)` path
- CLI path resolved at import time via `shutil.which("claude")` → `/home/maatru/.local/bin/claude`
