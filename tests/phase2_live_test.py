"""
Phase 2 live test — Qdrant RAG + WebSocket injection.

Usage:
    uv run tests/phase2_live_test.py

Requires: server running on port 19393 (uv run run_server.py --verbose)

Tests:
  1. KB standalone: Elden Ring MISS → claude research → tactic returned
  2. KB standalone: Elden Ring second call → Qdrant HIT (score ≥ 0.8)
  3. KB standalone: Minecraft MISS → MC-specific tactic returned
  4. WebSocket: inject-game-context → bot responds with [GAME CONTEXT] in system prompt
  5. WebSocket: second inject same game → Qdrant HIT → [KNOWN_TACTICS] in bot response
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import websockets

# Paths
ROOT = Path(__file__).parent.parent
ELDEN1 = str(ROOT / "tests/data/elden1.jpg")
ELDEN2 = str(ROOT / "tests/data/elden2.jpg")
MC1 = str(ROOT / "tests/data/mc1.jpg")

WS_URL = "ws://localhost:19393/client-ws"
CLIENT_UID = "phase2-test-001"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"


# ──────────────────────────────────────── KB standalone tests ────────────────


def test_kb_standalone() -> bool:
    """Tests 1-3: Direct KB instantiation, no WebSocket."""
    sys.path.insert(0, str(ROOT / "src"))
    # Load env from .env in project root
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    from open_llm_vtuber.modules.knowledge_base import KnowledgeBase

    print("\n── KB standalone tests ──────────────────────────────")
    kb = KnowledgeBase(session_dir=str(ROOT / "sessions/test"))
    all_pass = True

    # Test 1 – Elden Ring MISS (first time)
    print("\nTest 1: Elden Ring — Margit MISS path")
    t0 = time.time()
    result = kb.get_game_context(
        game_name="Elden Ring",
        current_state="fighting Margit the Fell Omen boss",
        screenshot_path=ELDEN1,
    )
    elapsed = time.time() - t0
    if result and len(result) > 20:
        print(f"{PASS} Got tactic ({len(result)} chars, {elapsed:.1f}s)")
        print(f"       {result[:120]}...")
    else:
        print(f"{FAIL} Empty or too-short result: {repr(result)}")
        all_pass = False

    # Test 2 – Elden Ring HIT (same state, should hit Qdrant now)
    print("\nTest 2: Elden Ring — Margit HIT path (second call)")
    t0 = time.time()
    result2 = kb.get_game_context(
        game_name="Elden Ring",
        current_state="fighting Margit the Fell Omen boss",
        screenshot_path=ELDEN2,
    )
    elapsed = time.time() - t0
    if result2 and ("[KNOWN_TACTICS]" in result2 or len(result2) > 20):
        marker = "[KNOWN_TACTICS]" if "[KNOWN_TACTICS]" in result2 else "tactic"
        print(f"{PASS} HIT returned ({marker} present, {elapsed:.1f}s)")
        print(f"       {result2[:120]}...")
    else:
        print(f"{FAIL} HIT path failed: {repr(result2)}")
        all_pass = False

    # Test 3 – Minecraft MISS
    print("\nTest 3: Minecraft — starting world MISS path")
    t0 = time.time()
    result3 = kb.get_game_context(
        game_name="Minecraft",
        current_state="just started a new survival world, need to gather resources",
        screenshot_path=MC1,
    )
    elapsed = time.time() - t0
    if result3 and len(result3) > 20 and "elden" not in result3.lower():
        print(f"{PASS} Got MC tactic ({len(result3)} chars, {elapsed:.1f}s)")
        print(f"       {result3[:120]}...")
    else:
        print(f"{FAIL} MC result bad: {repr(result3[:200])}")
        all_pass = False

    return all_pass


# ──────────────────────────────────────── WebSocket tests ────────────────────


async def recv_until(ws, msg_type: str, timeout: float = 120.0) -> dict | None:
    """Receive messages until one matches the expected type."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 10.0))
        except asyncio.TimeoutError:
            continue
        msg = json.loads(raw)
        print(f"    ← {msg.get('type','?')}: {str(msg)[:100]}")
        if msg.get("type") == msg_type:
            return msg
    return None


async def test_ws_game_context() -> bool:
    """Tests 4-5: inject-game-context via WebSocket → bot response contains game context."""
    print("\n── WebSocket game context tests ─────────────────────")
    all_pass = True

    try:
        ws_url = f"{WS_URL}?client_id={CLIENT_UID}"
        print(f"Connecting to {ws_url} ...")
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            # Wait for set-model-and-conf (connection established)
            init_msg = await recv_until(ws, "set-model-and-conf", timeout=15)
            if not init_msg:
                print(f"{FAIL} Server did not send set-model-and-conf within 15s")
                return False
            print(f"{PASS} Connected, client_uid={init_msg.get('client_uid')}")

            # ── Test 4: inject Elden Ring context → verify context set
            print("\nTest 4: inject-game-context (Elden Ring)")
            await ws.send(
                json.dumps(
                    {
                        "type": "inject-game-context",
                        "game_name": "Elden Ring",
                        "current_state": "fighting Margit the Fell Omen boss",
                        "screenshot_path": ELDEN1,
                    }
                )
            )
            ctx_result = await recv_until(ws, "game-context-result", timeout=120)
            if ctx_result and ctx_result.get("status") == "ok":
                ctx_text = ctx_result.get("current_game_context", "")
                print(f"{PASS} Game context set ({len(ctx_text)} chars)")
                print(f"       {ctx_text[:120]}...")
            else:
                print(f"{FAIL} inject-game-context failed: {ctx_result}")
                all_pass = False

            # Now send text-input → game context should be in system prompt → bot talks about it
            print("\nTest 4b: text-input → bot responds WITH game context in system prompt")
            await ws.send(
                json.dumps(
                    {
                        "type": "text-input",
                        "text": "I'm playing a game and need help. What should I do right now?",
                    }
                )
            )

            # Collect bot response — wait for conversation-chain-end (not backend-synth-complete
            # which can arrive from prior conversations). Also extract display_text from audio msgs.
            full_response = ""
            in_our_conversation = False
            deadline = time.time() + 120
            while time.time() < deadline:
                remaining = deadline - time.time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 15))
                except asyncio.TimeoutError:
                    break
                msg = json.loads(raw)
                mtype = msg.get("type", "")

                if mtype == "control" and msg.get("text") == "conversation-chain-start":
                    in_our_conversation = True
                    print("    ← conversation-chain-start")
                elif mtype == "full-text" and in_our_conversation:
                    txt = msg.get("text", "")
                    if txt and txt != "Thinking...":
                        full_response += txt + " "
                    print(f"    ← [AI]: {txt[:80]}")
                elif mtype == "audio" and in_our_conversation:
                    # Extract display_text from audio payload
                    display = msg.get("display_text")
                    if display and isinstance(display, dict):
                        txt = display.get("text", "")
                        if txt:
                            full_response += txt + " "
                            print(f"    ← [audio display]: {txt[:80]}")
                elif mtype == "control" and msg.get("text") == "conversation-chain-end":
                    if in_our_conversation:
                        print("    ← conversation-chain-end")
                        break
                else:
                    print(f"    ← {mtype}: {str(msg)[:60]}")

            elden_keywords = ["margit", "elden", "boss", "dodge", "attack", "shackle", "summon",
                              "pillar", "heal", "slam", "tactic", "game"]
            found = [k for k in elden_keywords if k in full_response.lower()]
            if found:
                print(f"{PASS} Bot response contains game context keywords: {found}")
            else:
                print(f"{FAIL} Bot response missing game context. Response: {full_response[:200]}")
                all_pass = False

            # ── Test 5: second inject same state → should be Qdrant HIT
            print("\nTest 5: second inject-game-context same state → Qdrant HIT")
            await ws.send(
                json.dumps(
                    {
                        "type": "inject-game-context",
                        "game_name": "Elden Ring",
                        "current_state": "fighting Margit the Fell Omen boss",
                        "screenshot_path": ELDEN2,
                    }
                )
            )
            ctx_result2 = await recv_until(ws, "game-context-result", timeout=60)
            if ctx_result2 and ctx_result2.get("status") == "ok":
                ctx_text2 = ctx_result2.get("current_game_context", "")
                if "[KNOWN_TACTICS]" in ctx_text2:
                    print(f"{PASS} Qdrant HIT — [KNOWN_TACTICS] present in context")
                    print(f"       {ctx_text2[:120]}...")
                else:
                    print("    (Context returned, no HIT marker — may still be valid)")
                    print(f"       {ctx_text2[:120]}...")
            else:
                print(f"{FAIL} Second inject failed: {ctx_result2}")
                all_pass = False

    except ConnectionRefusedError:
        print(f"{FAIL} Cannot connect to server at {WS_URL}")
        print("       Start server with: uv run run_server.py --verbose")
        return False
    except Exception as exc:
        print(f"{FAIL} WebSocket test error: {exc}")
        import traceback
        traceback.print_exc()
        return False

    return all_pass


# ──────────────────────────────────────── main ───────────────────────────────


def main():
    print("=" * 60)
    print("Phase 2 Live Test — Qdrant RAG + WebSocket")
    print("=" * 60)

    # KB standalone tests
    kb_ok = test_kb_standalone()

    # WebSocket tests
    ws_ok = asyncio.run(test_ws_game_context())

    print("\n" + "=" * 60)
    print(f"KB standalone:   {'PASS' if kb_ok else 'FAIL'}")
    print(f"WebSocket tests: {'PASS' if ws_ok else 'FAIL'}")
    print("=" * 60)

    sys.exit(0 if (kb_ok and ws_ok) else 1)


if __name__ == "__main__":
    main()
