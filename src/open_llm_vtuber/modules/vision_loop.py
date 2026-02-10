"""
vision_loop.py — Proactive screen watcher for gameplay detection.

Runs as a daemon thread per WebSocket session.
Every 15–25 s captures the Windows screen via PowerShell (WSL2 compatible).
Uses pHash Hamming distance to detect screen changes:
  < 5 → AFK / unchanged screen → skip
  ≥ 5 → screen changed → run KnowledgeBase.get_game_context → fire ai-speak-signal

Screenshots are saved to sessions/{client_uid}/screenshots/{timestamp}.png
"""

import asyncio
import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np
from loguru import logger

_PHASH_CHANGE_THRESHOLD = 5  # Hamming distance: < 5 = AFK, ≥ 5 = changed
_SCREENSHOT_INTERVAL_MIN = 15  # seconds
_SCREENSHOT_INTERVAL_MAX = 25  # seconds
_PS_TIMEOUT = 10  # seconds for PowerShell call
_MIN_TRIGGER_INTERVAL = 60  # minimum seconds between proactive AI speaks

_POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"


def _wsl_path_to_windows(linux_path: Path) -> str:
    """Convert Linux WSL path to Windows UNC path using wslpath."""
    result = subprocess.run(
        ["wslpath", "-w", str(linux_path)],
        capture_output=True,
        text=True,
        timeout=3,
    )
    return result.stdout.strip()


def _take_screenshot(path: Path) -> bool:
    """
    Capture the primary Windows screen via PowerShell WSL2 interop.
    Returns True if the screenshot file was written successfully.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    win_path = _wsl_path_to_windows(path)
    if not win_path:
        logger.warning("wslpath conversion failed — screenshot skipped")
        return False

    ps_script = (
        "Add-Type -AssemblyName System.Drawing,System.Windows.Forms; "
        "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp = New-Object System.Drawing.Bitmap($b.Width,$b.Height); "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size); "
        f"$bmp.Save('{win_path}'); "
        "$g.Dispose(); $bmp.Dispose()"
    )
    try:
        result = subprocess.run(
            [_POWERSHELL, "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=_PS_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning(f"PowerShell screenshot failed: {result.stderr[:200]}")
            return False
        return path.exists() and path.stat().st_size > 0
    except subprocess.TimeoutExpired:
        logger.warning("PowerShell screenshot timed out")
        return False
    except Exception as exc:
        logger.warning(f"Screenshot error: {exc}")
        return False


def _compute_phash(image_path: Path) -> Optional[np.ndarray]:
    """Compute pHash for the given image. Returns None on failure."""
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        hasher = cv2.img_hash.PHash_create()
        return hasher.compute(img)
    except Exception as exc:
        logger.warning(f"pHash computation failed: {exc}")
        return None


def _hamming_distance(h1: np.ndarray, h2: np.ndarray) -> float:
    """Compute Hamming distance between two pHash values."""
    try:
        hasher = cv2.img_hash.PHash_create()
        return float(hasher.compare(h1, h2))
    except Exception:
        return 100.0  # assume different on error


class ScreenWatcher:
    """
    Daemon thread that watches the user's screen and fires the conversation
    trigger when meaningful screen changes are detected (e.g., game state changes).

    trigger_fn: async callable(client_uid, context_text) that routes through
                the WebSocket handler's _handle_conversation_trigger.
    """

    def __init__(
        self,
        client_uid: str,
        session_dir: Path,
        knowledge_base,
        trigger_fn: Callable,
        event_loop: asyncio.AbstractEventLoop,
    ):
        self._client_uid = client_uid
        self._screenshots_dir = session_dir / "screenshots"
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._kb = knowledge_base
        self._trigger_fn = trigger_fn
        self._loop = event_loop

        self._stop_event = threading.Event()
        self._last_hash: Optional[np.ndarray] = None
        self._thread: Optional[threading.Thread] = None
        self._last_trigger_time: float = 0.0  # unix timestamp of last proactive speak

    def start(self) -> None:
        """Start the screen watcher daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning(f"ScreenWatcher already running for {self._client_uid}")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop,
            name=f"screen-watcher-{self._client_uid}",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"ScreenWatcher started for client={self._client_uid}")

    def stop(self) -> None:
        """Signal the watcher thread to stop."""
        self._stop_event.set()
        logger.info(f"ScreenWatcher stopped for client={self._client_uid}")

    # ---------------------------------------------------------------- internals

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            interval = random.uniform(_SCREENSHOT_INTERVAL_MIN, _SCREENSHOT_INTERVAL_MAX)
            self._stop_event.wait(timeout=interval)
            if self._stop_event.is_set():
                break

            timestamp = int(time.time())
            path = self._screenshots_dir / f"{timestamp}.png"

            if not _take_screenshot(path):
                continue

            current_hash = _compute_phash(path)
            if current_hash is None:
                continue

            if self._last_hash is not None:
                dist = _hamming_distance(self._last_hash, current_hash)
                if dist < _PHASH_CHANGE_THRESHOLD:
                    logger.debug(f"AFK detected (hamming={dist:.0f}) — skipping")
                    path.unlink(missing_ok=True)
                    continue
                logger.info(f"Screen change detected (hamming={dist:.0f}) — analyzing")
            else:
                logger.info("First screenshot captured — analyzing")

            self._last_hash = current_hash
            self._analyze_screen(path)

    def _analyze_screen(self, screenshot_path: Path) -> None:
        """Get game context from KnowledgeBase and trigger AI to speak proactively."""
        if self._kb is None:
            return

        # Enforce cooldown — don't spam proactive speaks
        now = time.time()
        if now - self._last_trigger_time < _MIN_TRIGGER_INTERVAL:
            remaining = _MIN_TRIGGER_INTERVAL - (now - self._last_trigger_time)
            logger.debug(f"Vision loop cooldown active ({remaining:.0f}s remaining) — skipping")
            return

        try:
            context = self._kb.get_game_context(
                game_name="unknown",
                current_state="active gameplay",
                screenshot_path=str(screenshot_path),
            )
            if not context or len(context) < 30:
                return

            self._last_trigger_time = time.time()
            # Route through conversation trigger (ai-speak-signal) on the event loop
            future = asyncio.run_coroutine_threadsafe(
                self._trigger_fn(context), self._loop
            )
            future.result(timeout=10)
            logger.info(f"Vision loop triggered AI response ({len(context)} chars)")
        except Exception as exc:
            logger.warning(f"Vision loop analyze error: {exc}")
