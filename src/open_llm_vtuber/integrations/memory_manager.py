"""
memory_manager.py — Supabase persistent memory layer.

Tables (auto-created on first use via REST upsert):
  user_history     : (user_id, game_name, advice_given, user_reaction, timestamp)
  chat_logs        : (user_id, session_id, chat_history jsonb, chat_summary, timestamp)
  long_term_profile: (user_id, bot_id, preferences_json jsonb)

Usage:
  mm = MemoryManager(user_id="uid", bot_id="mao_pro")
  mm.save_advice(game_name, advice)
  mm.save_chat_log(session_id, history, summary)
  profile = mm.get_long_term_profile()  -> injected into system prompt
  mm.update_profile(new_prefs)
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from loguru import logger
from supabase import create_client, Client

load_dotenv()


class MemoryManager:
    """Supabase-backed persistent memory for a single user/bot session."""

    def __init__(self, user_id: str, bot_id: str = "mao_pro"):
        self.user_id = user_id
        self.bot_id = bot_id

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env")

        self._db: Client = create_client(url, key)
        logger.info(f"MemoryManager ready. user_id={user_id} bot_id={bot_id}")

    # ----------------------------------------------------------------- public

    def save_advice(
        self,
        game_name: str,
        advice_given: str,
        user_reaction: str = "unknown",
    ) -> None:
        """Insert a row into user_history after each advice is given."""
        try:
            self._db.table("user_history").insert({
                "user_id": self.user_id,
                "game_name": game_name,
                "advice_given": advice_given,
                "user_reaction": user_reaction,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.debug(f"Advice saved to user_history for {self.user_id}/{game_name}")
        except Exception as exc:
            logger.warning(f"save_advice failed: {exc}")

    def save_chat_log(
        self,
        session_id: str,
        chat_history: list[dict],
        chat_summary: str = "",
    ) -> None:
        """Upsert full session chat log into chat_logs (on session end or timer)."""
        try:
            self._db.table("chat_logs").upsert({
                "user_id": self.user_id,
                "session_id": session_id,
                "chat_history": json.dumps(chat_history),
                "chat_summary": chat_summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.debug(f"Chat log saved for session={session_id}")
        except Exception as exc:
            logger.warning(f"save_chat_log failed: {exc}")

    def get_long_term_profile(self) -> dict[str, Any]:
        """
        Fetch persistent preferences for this user/bot pair.
        Returns empty dict if no profile exists yet.
        """
        try:
            result = (
                self._db.table("long_term_profile")
                .select("preferences_json")
                .eq("user_id", self.user_id)
                .eq("bot_id", self.bot_id)
                .limit(1)
                .execute()
            )
            if result.data and result.data[0].get("preferences_json"):
                prefs = result.data[0]["preferences_json"]
                if isinstance(prefs, str):
                    prefs = json.loads(prefs)
                logger.debug(f"Loaded long_term_profile for {self.user_id}")
                return prefs
        except Exception as exc:
            logger.warning(f"get_long_term_profile failed: {exc}")
        return {}

    def update_profile(self, new_preferences: dict[str, Any]) -> None:
        """Upsert long_term_profile with merged preferences."""
        try:
            existing = self.get_long_term_profile()
            merged = {**existing, **new_preferences}
            self._db.table("long_term_profile").upsert({
                "user_id": self.user_id,
                "bot_id": self.bot_id,
                "preferences_json": json.dumps(merged),
            }).execute()
            logger.debug(f"Updated long_term_profile for {self.user_id}")
        except Exception as exc:
            logger.warning(f"update_profile failed: {exc}")

    def get_recent_advice(self, game_name: Optional[str] = None, limit: int = 5) -> list[dict]:
        """Fetch recent advice rows for context injection."""
        try:
            query = (
                self._db.table("user_history")
                .select("game_name, advice_given, user_reaction, timestamp")
                .eq("user_id", self.user_id)
                .order("timestamp", desc=True)
                .limit(limit)
            )
            if game_name:
                query = query.eq("game_name", game_name)
            result = query.execute()
            return result.data or []
        except Exception as exc:
            logger.warning(f"get_recent_advice failed: {exc}")
            return []

    def build_profile_prompt(self) -> str:
        """
        Build a system prompt fragment from long_term_profile + recent advice.
        Called by service_context.construct_system_prompt().
        """
        lines = []
        profile = self.get_long_term_profile()
        if profile:
            lines.append("[USER PROFILE]")
            for k, v in profile.items():
                lines.append(f"  {k}: {v}")

        recent = self.get_recent_advice(limit=3)
        if recent:
            lines.append("[RECENT ADVICE GIVEN]")
            for row in recent:
                ts = row.get("timestamp", "")[:16]
                lines.append(
                    f"  [{ts}] {row.get('game_name','?')}: {row.get('advice_given','')[:120]}"
                    f" (reaction: {row.get('user_reaction','?')})"
                )
        return "\n".join(lines) if lines else ""
