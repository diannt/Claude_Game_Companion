import json
import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import AsyncIterator, List, Dict, Any

from loguru import logger
from .stateless_llm_interface import StatelessLLMInterface

# Resolve claude CLI path at import time; fall back to known install location
_CLAUDE_CLI = shutil.which("claude") or "/home/maatru/.local/bin/claude"


class WSLClaudeLLM(StatelessLLMInterface):
    """LLM backend that runs the local `claude -p` subprocess.

    No API keys, no network LLM calls. Invokes the Claude CLI installed on the
    host and streams the single-turn response back as one text chunk.
    """

    def __init__(self, system: str = "", session_dir: str = "sessions", **kwargs):
        self._system = system
        self._session_dir = Path(session_dir)
        self._session_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"WSLClaudeLLM ready. CLI={_CLAUDE_CLI} session_dir={self._session_dir}"
        )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(self, messages: List[Dict[str, Any]], system: str) -> str:
        """Flatten system + conversation history into a single -p prompt string."""
        sys_block = (system or self._system).strip()
        json_schema = (
            "\n\nCRITICAL: Respond ONLY with valid JSON — no markdown, no extra text.\n"
            'Schema: {"text": "<response>", "emotion": "<emotion_name>", "action": "none"}\n'
        )
        sys_block = sys_block + json_schema

        history_lines: List[str] = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            if isinstance(content, list):
                # Flatten multi-part content blocks (text + image)
                content = " ".join(
                    c.get("text", "")
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                )
            history_lines.append(f"{role}: {content}")

        return f"{sys_block}\n\n" + "\n".join(history_lines) + "\n\nASSISTANT:"

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        system: str = None,
        tools: List[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Run `claude -p <prompt>` and yield the response as a single text chunk."""
        prompt = self._build_prompt(messages, system)
        loop = asyncio.get_event_loop()
        result = None

        for attempt in range(3):
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda p=prompt: subprocess.run(
                        [_CLAUDE_CLI, "-p", p],
                        capture_output=True,
                        text=True,
                        cwd=str(self._session_dir),
                        timeout=120,
                    ),
                )
                if result.returncode == 0:
                    break
                logger.warning(
                    f"WSL Claude attempt {attempt + 1} failed "
                    f"(rc={result.returncode}): {result.stderr[:200]}"
                )
            except subprocess.TimeoutExpired:
                logger.warning(f"WSL Claude attempt {attempt + 1} timed out (120s)")
            except Exception as exc:
                logger.warning(f"WSL Claude attempt {attempt + 1} error: {exc}")

            if attempt < 2:
                await asyncio.sleep(1)
            else:
                err = (result.stderr[:500] if result else "subprocess error")
                raise RuntimeError(f"claude -p failed after 3 attempts: {err}")

        raw = (result.stdout or "").strip()
        logger.debug(f"WSL Claude raw output ({len(raw)} chars): {raw[:300]}")

        # Strip markdown code fences (Claude often wraps JSON in ```json ... ```)
        cleaned = raw
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Remove first line (```json or ```) and last line (```)
            inner = lines[1:] if len(lines) > 2 else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            cleaned = "\n".join(inner).strip()

        # Try to extract `text` from JSON response; fall back to raw output
        try:
            data = json.loads(cleaned)
            text = data.get("text", raw)
        except (json.JSONDecodeError, AttributeError):
            text = raw

        yield text or "[No response]"
