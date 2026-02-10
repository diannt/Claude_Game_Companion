# Phase 3: Proactive Gameplay Vision Loop

## Start: 2026-02-10T10:43:29Z

## Scope
- `src/open_llm_vtuber/modules/vision_loop.py` — ScreenWatcher daemon thread
- `src/open_llm_vtuber/websocket_handler.py` — start/stop vision loop on connect/disconnect

## Implementation
1. `ScreenWatcher` daemon thread: every 15–25s takes screenshot via `pyautogui`
2. pHash comparison with `cv2.img_hash.PHash_create()` — Hamming < 5 → AFK, skip
3. On screen change: calls `knowledge_base.get_game_context()` → fires `ai-speak-signal` through WebSocket
4. Screenshots saved to `sessions/{client_uid}/screenshots/{timestamp}.png`

## Tests
- [ ] ScreenWatcher starts and stops cleanly
- [ ] pHash AFK detection works (static screen skipped)
- [ ] Screen change triggers ai-speak-signal through websocket
- [ ] Screenshots saved to correct session dir

## End: TBD
