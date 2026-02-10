# Phase 3: Proactive Gameplay Vision Loop

## Start: 2026-02-10T10:43:29Z

## Scope
- `src/open_llm_vtuber/modules/vision_loop.py` — ScreenWatcher daemon thread
- `src/open_llm_vtuber/websocket_handler.py` — start/stop vision loop on connect/disconnect

## Implementation
1. `ScreenWatcher` daemon thread: every 15–25s takes screenshot via PowerShell WSL2 interop
2. pHash comparison with `cv2.img_hash.PHash_create()` — Hamming < 5 → AFK, skip
3. 60s cooldown between proactive triggers (prevents spam)
4. On screen change: calls `knowledge_base.get_game_context()` → fires `ai-speak-signal` through WebSocket
5. Screenshots saved to `sessions/{client_uid}/screenshots/{timestamp}.png`

## Conversation Quality Fixes (same commit)
- `ai-speak-signal` blocked if a conversation task is already running (no interruption)
- Response length capped to 1–2 sentences via system prompt rule

## Live Test Results (2026-02-10)

**Step 1: Display Elden Ring screenshot fullscreen via PowerShell**
- Opened `tests/data/elden1.jpg` fullscreen on Windows display → PASS

**Step 2: Capture screen via PowerShell (_take_screenshot)**
- Screenshot file: `sessions/phase3-test/screenshots/1770726007.png`
- File size: 3,169,232 bytes (full 1920×1080 capture)
- Result: **PASS**

**Step 3: pHash computation**
- Hash computed: `e9b5ead6cbfef9dd...`
- Result: **PASS**

**Step 4: KnowledgeBase.get_game_context() on captured screenshot**
- Pipeline ran end-to-end, context returned
- Result: **PASS**

## Vision Fix (post Phase-3 patch)

Previous implementation passed the screenshot as a text path string — Claude could not
see the image. Fixed by prefixing the path with `@` in the prompt:

```
@/path/to/screenshot.png

Look at this gameplay screenshot. Identify the game...
```

The `claude -p` CLI reads and analyzes the image directly.  The 120s timeout was also
removed — research completes however long it takes, then saves to Qdrant + Supabase.

After the first identification, `KnowledgeBase.current_game_name` is set and the vision
loop reuses it for subsequent Qdrant lookups (avoids redundant Claude calls for same game).

## End: 2026-02-10T04:23:00Z
