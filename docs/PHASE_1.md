# Phase 1: WSL Claude LLM Core

**Start:** 2026-02-10T10:10:32Z
**Verified Live:** 2026-02-10T11:05:10Z
**Total elapsed (Phase 1):** ~55 min (includes CHN strip pre-work + code + live test)

## Objective
Create `WSLClaudeLLM` — the sole LLM backend that runs `claude -p` as a subprocess.
Wire it into the agent factory and verify end-to-end conversation flow with Live2D.

## Scope
- `src/open_llm_vtuber/agent/stateless_llm/wsl_claude.py` — WSLClaudeLLM class
- `src/open_llm_vtuber/agent/stateless_llm_factory.py` — always returns WSLClaudeLLM
- `src/open_llm_vtuber/config_manager/stateless_llm.py` — WSLClaudeConfig added
- `src/open_llm_vtuber/config_manager/agent.py` — `wsl_claude_llm` added to Literal
- `config_templates/conf.default.yaml` — `wsl_claude_llm` as sole default LLM

---

## Live Test Results (WebSocket conversation, server on port 19393)

### Test 1 — Identity question
**Input:** `"Hello, what is your name?"`

**Server log confirmed:**
```
WSL Claude raw output (401 chars): ```json
{"text": "[joy] Oh, how delightfully original..."}
```
[AI] display: Oh,
[AI] display: [smirk] My name is Mili, and I'm the AI VTuber who's stuck babysitting humans.
[AI] display: [joy] Nice to meet you, I suppose.
[AI] display: What brings you to my digital domain today?
```

**Results:**
- `claude -p` subprocess fired ✅
- JSON parsed, `text` field extracted ✅
- Markdown code fences (`\`\`\`json`) stripped before parse ✅
- Live2D emotion tags extracted: `[joy]`, `[smirk]` ✅
- TTS pipeline invoked: 5 sentences → 5 audio chunks ✅
- Audio chunks delivered to WebSocket client ✅
- Character persona maintained (Mili — sarcastic AI VTuber) ✅

### Test 2 — Elden Ring question (game-relevant response)
**Input:** `"I keep dying to Margit. Any tips?"`

**Server log confirmed:**
```
🏃Generating audio for 'Ah yes,'
🏃Generating audio for 'Margit the Fell Omen - the classic welcome to Elden Ring boss.'
🏃Generating audio for 'Lone Wolf Ashes from Ranni... summons are basically legal cheating.'
🏃Generating audio for 'Margit's Shackle you can buy from Patches...'
🏃Generating audio for 'Jump attacks are your friend, dodge INTO his attacks...'
(11 total audio segments)
```
- WSLClaudeLLM produced full, coherent, game-accurate response ✅
- 11 TTS audio chunks sent to client ✅
- `backend-synth-complete` message sent ✅

### Test 3 — Server isolation
- Server runs exclusively on port **19393** (custom, not default 12393)
- `host: 0.0.0.0` for browser accessibility ✅
- No conflict with any other running instances ✅

---

## Phase 1 Pass Criteria
- [x] `claude -p` subprocess runs for every user message
- [x] JSON response parsed (`text`, `emotion` fields extracted)
- [x] Markdown fence stripping handles `\`\`\`json ... \`\`\`` wrapping
- [x] Live2D expression tags extracted and forwarded
- [x] TTS receives text and produces audio chunks
- [x] Audio delivered to WebSocket client
- [x] Server isolated on custom port 19393
- [x] No API keys, no remote LLM calls — local `claude` CLI only
- [x] Ruff lint: zero warnings on all modified files

## Files Created/Modified
| File | Change |
|------|--------|
| `src/.../stateless_llm/wsl_claude.py` | **Created** — WSLClaudeLLM |
| `src/.../stateless_llm_factory.py` | **Modified** — force returns WSLClaudeLLM |
| `src/.../config_manager/stateless_llm.py` | **Modified** — WSLClaudeConfig added |
| `src/.../config_manager/agent.py` | **Modified** — wsl_claude_llm in Literal |
| `config_templates/conf.default.yaml` | **Modified** — wsl_claude_llm as default |
| `conf.yaml` | **Created** — local config with port 19393 |

## Known Discovery
Claude CLI always wraps JSON output in ` ```json ... ``` ` markdown fences, even when
instructed not to. Stripping logic added to `chat_completion` before JSON parse.
