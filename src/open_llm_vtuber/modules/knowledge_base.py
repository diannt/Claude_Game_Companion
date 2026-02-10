"""
knowledge_base.py — Qdrant RAG for game knowledge.

Uses Qdrant cloud inference (no local embeddings model).
Collection: game_knowledge  (384-dim Cosine, sentence-transformers/all-minilm-l6-v2)

Flow:
  get_game_context(game, state, screenshot?) →
    Qdrant search (score ≥ 0.8) → "[KNOWN_TACTICS]: {tactic}"
    miss → claude -p research → ingest tactic + best_practices → return tactic
"""

import os
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    PointStruct,
    Distance,
    VectorParams,
    Document,
)

load_dotenv()

_CLAUDE_CLI = shutil.which("claude") or "/home/maatru/.local/bin/claude"
_COLLECTION = "game_knowledge"
_MODEL = "sentence-transformers/all-minilm-l6-v2"
_HIT_THRESHOLD = 0.8


class KnowledgeBase:
    """Qdrant-backed game knowledge store with claude research fallback."""

    def __init__(self, session_dir: str = "sessions"):
        self._session_dir = Path(session_dir)
        self._session_dir.mkdir(parents=True, exist_ok=True)

        api_key = os.getenv("QDRANT_API_KEY")
        endpoint = os.getenv("QDRANT_CLUSTER_ENDPOINT")
        if not api_key or not endpoint:
            raise ValueError(
                "QDRANT_API_KEY and QDRANT_CLUSTER_ENDPOINT must be set in .env"
            )

        self._client = QdrantClient(
            url=endpoint,
            api_key=api_key,
            cloud_inference=True,
        )
        self._ensure_collection()
        self.current_game_context: str = ""
        self.current_game_name: str = ""
        logger.info(f"KnowledgeBase ready. collection={_COLLECTION}")

    # ------------------------------------------------------------------ public

    def get_game_context(
        self,
        game_name: str,
        current_state: str,
        screenshot_path: Optional[str] = None,
    ) -> str:
        """
        Return game context string for system prompt injection.

        When game_name is "unknown" and a screenshot is provided, Claude visually
        identifies the game first (skip Qdrant — nothing is indexed under "unknown").

        Otherwise:
          Hit  → "[KNOWN_TACTICS]: {tactic}"
          Miss → runs claude research, ingests to Qdrant, returns tactic string
        """
        if game_name != "unknown":
            query_text = f"{game_name}: {current_state}"
            try:
                results = self._client.query_points(
                    collection_name=_COLLECTION,
                    query=Document(text=query_text, model=_MODEL),
                    limit=1,
                    score_threshold=_HIT_THRESHOLD,
                    with_payload=True,
                )
                hits = results.points if hasattr(results, "points") else []
                if hits:
                    tactic = hits[0].payload.get("tactic", "")
                    score = hits[0].score
                    logger.info(
                        f"Qdrant HIT score={score:.3f} game={game_name} state={current_state}"
                    )
                    context = f"[KNOWN_TACTICS]: {tactic}"
                    self.current_game_context = context
                    self.current_game_name = game_name
                    return context
            except Exception as exc:
                logger.warning(f"Qdrant search error: {exc}")

        # --- miss or unknown game: research with claude
        logger.info(f"Qdrant MISS — researching {game_name}/{current_state}")
        tactic, best_practices, identified_game, identified_state = self._research_with_claude(
            game_name, current_state, screenshot_path
        )
        self._ingest(identified_game, identified_state, tactic, best_practices)
        self.current_game_context = tactic
        self.current_game_name = identified_game
        return tactic

    # --------------------------------------------------------------- internals

    def _ensure_collection(self) -> None:
        """Auto-create game_knowledge collection if absent."""
        try:
            names = [c.name for c in self._client.get_collections().collections]
        except Exception as exc:
            logger.error(f"Failed to list Qdrant collections: {exc}")
            return

        if _COLLECTION not in names:
            logger.info(f"Creating Qdrant collection '{_COLLECTION}'...")
            self._client.create_collection(
                collection_name=_COLLECTION,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info(f"Collection '{_COLLECTION}' created.")
        else:
            logger.info(f"Collection '{_COLLECTION}' found in Qdrant cloud.")

    def _research_with_claude(
        self,
        game_name: str,
        current_state: str,
        screenshot_path: Optional[str],
    ) -> tuple[str, str, str, str]:
        """
        Run `claude -p` to research the game/state visually.
        When screenshot_path is provided, prefixes @/path in the prompt so
        Claude CLI loads and analyzes the image directly.
        Returns (tactic, best_practices, identified_game_name, identified_state).
        No timeout — research completes however long it takes.
        """
        if screenshot_path:
            prompt = (
                f"@{screenshot_path}\n\n"
                "Look at this gameplay screenshot. Identify the game and what is currently happening.\n"
                "Return ONLY a JSON object (no markdown fences) with exactly these keys:\n"
                '{"game_name":"...","current_state":"...","tactic":"...","best_practices_3000_symbols":"..."}\n\n'
                "game_name: the exact name of the game shown in the screenshot.\n"
                "current_state: brief description of what is happening right now "
                "(e.g. 'boss fight: Margit the Fell Omen', 'exploring open world', 'low health emergency').\n"
                "tactic: 2-3 sentences of specific actions the player should take RIGHT NOW.\n"
                "best_practices_3000_symbols: comprehensive gameplay guide for this game/situation (≤3000 chars)."
            )
        else:
            prompt = (
                f"The user is playing '{game_name}'. Current game state: '{current_state}'.\n\n"
                "Return ONLY a JSON object (no markdown fences) with exactly these keys:\n"
                '{"game_name":"...","current_state":"...","tactic":"...","best_practices_3000_symbols":"..."}\n\n'
                "tactic: 2-3 sentences of specific actions the player should take RIGHT NOW.\n"
                "best_practices_3000_symbols: comprehensive gameplay guide for this game/situation (≤3000 chars)."
            )

        try:
            result = subprocess.run(
                [_CLAUDE_CLI, "-p", prompt],
                capture_output=True,
                text=True,
                cwd=str(self._session_dir),
            )
            raw = (result.stdout or "").strip()
        except Exception as exc:
            logger.warning(f"claude research subprocess failed: {exc}")
            raw = ""

        # strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            inner = lines[1:] if len(lines) > 2 else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            raw = "\n".join(inner).strip()

        try:
            data = json.loads(raw)
            tactic = data.get("tactic", "")
            best_practices = data.get("best_practices_3000_symbols", "")
            identified_game = data.get("game_name") or game_name
            identified_state = data.get("current_state") or current_state
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"Research JSON parse failed; raw[:200]={raw[:200]}")
            tactic = raw[:500] if raw else f"Play carefully in {game_name}: {current_state}"
            best_practices = ""
            identified_game = game_name
            identified_state = current_state

        return (
            tactic or f"Adapt to {current_state} in {game_name}.",
            best_practices,
            identified_game,
            identified_state,
        )

    def _ingest(
        self,
        game_name: str,
        current_state: str,
        tactic: str,
        best_practices: str,
    ) -> None:
        """Upsert tactic and best_practices points into Qdrant."""
        points: list[PointStruct] = [
            PointStruct(
                id=str(uuid.uuid4()),
                payload={
                    "game_name": game_name,
                    "current_state": current_state,
                    "tactic": tactic,
                    "type": "tactic",
                },
                vector=Document(
                    text=f"{game_name}: {current_state}",
                    model=_MODEL,
                ),
            )
        ]

        if best_practices:
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    payload={
                        "game_name": game_name,
                        "current_state": current_state,
                        "tactic": best_practices,
                        "type": "best_practices",
                    },
                    vector=Document(
                        text=f"{game_name} general gameplay: {current_state}",
                        model=_MODEL,
                    ),
                )
            )

        try:
            self._client.upsert(collection_name=_COLLECTION, points=points)
            logger.info(
                f"Ingested {len(points)} Qdrant point(s) for {game_name}/{current_state}"
            )
        except Exception as exc:
            logger.error(f"Qdrant ingest failed: {exc}")
