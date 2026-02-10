# PLAN.md — Gameplay Companion Transformation

Forking Open-LLM-VTuber into a self-learning gameplay companion for the Player2 platform.

## Overview

| Phase | Scope | Key Deliverable |
|-------|-------|-----------------|
| Pre-work | CHN full strip | English-only codebase |
| 1 | WSL Claude LLM | `wsl_claude.py` — sole LLM provider |
| 2 | Qdrant RAG | `knowledge_base.py` — game tactics memory |
| 3 | Vision loop | `vision_loop.py` — proactive screen analysis |
| 4 | Supabase + Player2 | `memory_manager.py` + publication pipeline |
| 5 | E2E simulation | `tests/simulation.py` — full pipeline test |

---

## Pre-work: CHN Full Strip

### Files to delete
```
src/open_llm_vtuber/live/bilibili_live.py
src/open_llm_vtuber/asr/fun_asr.py
src/open_llm_vtuber/tts/cosyvoice_tts.py
src/open_llm_vtuber/tts/cosyvoice2_tts.py
src/open_llm_vtuber/tts/minimax_tts.py
src/open_llm_vtuber/tts/spark_tts.py
src/open_llm_vtuber/tts/siliconflow_tts.py
config_templates/conf.ZH.default.yaml
characters/zh_米粒.yaml
characters/zh_翻译腔.yaml
README.CN.md  (if present)
README.JP.md  (if present)
README.KR.md  (if present)
```

### Files to modify

| File | Change |
|------|--------|
| `tts/tts_factory.py` | Remove: cosyvoice, cosyvoice2, minimax, spark, siliconflow |
| `asr/asr_factory.py` | Remove: fun_asr |
| `config_manager/tts.py` | Remove config classes + Union entries for removed engines |
| `config_manager/asr.py` | Remove FunASRConfig + Union entry |
| `config_manager/live.py` | Remove BiliBiliLiveConfig; simplify to empty LiveConfig |
| `config_manager/stateless_llm.py` | Remove ZhipuConfig, DeepseekConfig + Union entries |
| `agent/stateless_llm_factory.py` | Remove zhipu_llm, deepseek_llm mappings |
| `config_manager/i18n.py` | Remove `zh` field; return `en` value directly in all methods |
| `config_templates/conf.default.yaml` | Remove CHN TTS/ASR/LLM sections |
| `pyproject.toml` | Remove `[project.optional-dependencies] bilibili` group |

---

## Phase 1: WSL Claude LLM Core

### New: `src/open_llm_vtuber/agent/stateless_llm/wsl_claude.py`

```python
"""WSL Claude LLM — runs `claude -p` subprocess as the sole LLM backend."""
import asyncio, json, subprocess
from pathlib import Path
from typing import AsyncIterator
from loguru import logger
from .stateless_llm_interface import StatelessLLMInterface

JSON_SCHEMA_INSTRUCTION = (
    "\n\nCRITICAL: Respond ONLY with a single valid JSON object. Schema:\n"
    '{"text": "<response with optional [emotion] tags>", '
    '"emotion": "<emotion_name>", "action": "none"}\n'
    "No prose, no markdown, no text outside this JSON object.\n\n"
)

class WSLClaudeLLM(StatelessLLMInterface):
    def __init__(self, system: str = None, session_dir: str = "sessions", **kwargs):
        self._system = system or ""
        self._session_dir = Path(session_dir)
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def _build_prompt(self, messages: list[dict], system: str | None) -> str:
        sys_block = (system or self._system) + JSON_SCHEMA_INSTRUCTION
        lines = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") for c in content if c.get("type") == "text"
                )
            lines.append(f"{role}: {content}")
        return f"{sys_block}\n\n" + "\n".join(lines) + "\n\nASSISTANT:"

    async def chat_completion(
        self,
        messages: list[dict],
        system: str = None,
        tools: list[dict] = None,
    ) -> AsyncIterator[str]:
        prompt = self._build_prompt(messages, system)
        loop = asyncio.get_event_loop()

        for attempt in range(3):
            result = await loop.run_in_executor(
                None,
                lambda p=prompt: subprocess.run(
                    ["claude", "-p", p],
                    capture_output=True,
                    text=True,
                    cwd=str(self._session_dir),
                    timeout=120,
                ),
            )
            if result.returncode == 0:
                break
            logger.warning(f"WSLClaudeLLM attempt {attempt+1}/3 failed: {result.stderr[:300]}")
            if attempt == 2:
                raise RuntimeError(f"claude -p failed after 3 attempts:\n{result.stderr}")
            await asyncio.sleep(1)

        raw = result.stdout.strip()
        try:
            data = json.loads(raw)
            yield data.get("text", raw)
        except json.JSONDecodeError:
            logger.debug(f"WSLClaudeLLM: non-JSON output, using raw: {raw[:100]}")
            yield raw
```

### Modify: `src/open_llm_vtuber/agent/stateless_llm_factory.py`

- Import `WSLClaudeLLM`
- Add `"wsl_claude_llm"` → `WSLClaudeLLM` mapping
- At the top of `create_llm()`, force override: `llm_provider = "wsl_claude_llm"`

### Modify: `src/open_llm_vtuber/config_manager/stateless_llm.py`

Add:
```python
class WSLClaudeConfig(BaseModel):
    session_dir: str = Field("sessions")
    interrupt_method: Literal["system", "user"] = Field("user")
```
Add to `StatelessLLMConfigs` union.

### Modify: `config_templates/conf.default.yaml`

```yaml
agent_settings:
  basic_memory_agent:
    llm_provider: 'wsl_claude_llm'
    faster_first_response: true
    segment_method: 'pysbd'
    use_mcpp: false

llm_configs:
  wsl_claude_llm:
    session_dir: 'sessions'
    interrupt_method: 'user'
```

### Modify: `src/open_llm_vtuber/websocket_handler.py`

On new connection — create session directory:
```python
session_dir = Path("sessions") / client_uid / str(uuid.uuid4())
(session_dir / "screenshots").mkdir(parents=True, exist_ok=True)
self._client_session_dirs[client_uid] = session_dir
```

### Phase 1 Test

```bash
uv run run_server.py --verbose
# → Open http://localhost:12393, send a text message
# → Logs should show: subprocess.run(['claude', '-p', ...])
# → JSON text field drives TTS output
```

---

## Phase 2: Qdrant RAG Knowledge Base

### New dependencies (`pyproject.toml`)
```
"qdrant-client>=1.11.0"
"python-dotenv>=1.0.0"
```

### Collection spec
- Name: `game_knowledge`
- Vectors: 384-dim, Cosine distance
- Cloud inference: `sentence-transformers/all-minilm-l6-v2`
- Payload schema: `{game_name, current_state, tactic, type, timestamp}`

### New: `src/open_llm_vtuber/modules/__init__.py` (empty)

### New: `src/open_llm_vtuber/modules/knowledge_base.py`

```python
"""Qdrant-backed game knowledge retrieval and research."""
import os, json, subprocess, uuid
from dotenv import load_dotenv
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    PointStruct, Document, Distance, VectorParams
)

RESEARCH_PROMPT = """The user is playing a game. Screenshot path: `{screenshot_path}`.
Return ONLY valid JSON (no other text):
{{"game_name":"...","current_state":"...","tactic":"...","best_practices_3000_symbols":"..."}}"""

class KnowledgeBase:
    COLLECTION = "game_knowledge"
    MODEL = "sentence-transformers/all-minilm-l6-v2"

    def __init__(self):
        load_dotenv()
        self.client = QdrantClient(
            url=os.environ["QDRANT_CLUSTER_ENDPOINT"],
            api_key=os.environ["QDRANT_API_KEY"],
            cloud_inference=True,
        )
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.COLLECTION not in existing:
            self.client.create_collection(
                self.COLLECTION,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection '{self.COLLECTION}'")

    async def get_game_context(
        self, game_name: str, current_state: str, screenshot_path: str = None
    ) -> str:
        query = f"{game_name}: {current_state}"
        results = self.client.query_points(
            collection_name=self.COLLECTION,
            query=Document(text=query, model=self.MODEL),
            score_threshold=0.8,
            limit=1,
        )
        if results.points:
            tactic = results.points[0].payload.get("tactic", "")
            logger.debug(f"Qdrant cache hit for '{query}'")
            return f"[KNOWN_TACTICS]: {tactic}"

        if screenshot_path:
            return await self._research_and_store(game_name, current_state, screenshot_path)
        return ""

    async def _research_and_store(
        self, game_name: str, current_state: str, screenshot_path: str
    ) -> str:
        import asyncio
        prompt = RESEARCH_PROMPT.format(screenshot_path=screenshot_path)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True, text=True, timeout=180
            )
        )
        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            logger.error(f"Knowledge base research: bad JSON from claude: {result.stdout[:200]}")
            return ""

        self._upsert(data["game_name"], data["current_state"], data["tactic"], "tactic")
        self._upsert(
            data["game_name"], "general",
            data.get("best_practices_3000_symbols", ""), "best_practices"
        )
        return f"[KNOWN_TACTICS]: {data['tactic']}"

    def _upsert(self, game_name: str, current_state: str, tactic: str, type_: str):
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                payload={"game_name": game_name, "current_state": current_state,
                         "tactic": tactic, "type": type_},
                vector=Document(
                    text=f"{game_name}: {current_state}", model=self.MODEL
                ),
            )]
        )
        logger.debug(f"Qdrant upsert: {game_name}/{current_state} [{type_}]")
```

### Modify: `src/open_llm_vtuber/service_context.py`

- Add `knowledge_base: KnowledgeBase | None = None`
- In `load_from_config()`: `self.knowledge_base = KnowledgeBase()`
- In `construct_system_prompt()`: accept optional `game_context: str` param, prepend if provided

### Phase 2 Test

```python
# Run directly:
from src.open_llm_vtuber.modules.knowledge_base import KnowledgeBase
import asyncio
kb = KnowledgeBase()
# First call — should trigger research (Qdrant empty)
ctx = asyncio.run(kb.get_game_context("Elden Ring", "boss fight Malenia", "tests/data/elden1.jpg"))
print(ctx)
# Second call — should hit Qdrant cache (score ≥ 0.8)
ctx2 = asyncio.run(kb.get_game_context("Elden Ring", "boss fight Malenia"))
print(ctx2)  # [KNOWN_TACTICS]: ...
```

---

## Phase 3: Vision Loop

### New dependencies (`pyproject.toml`)
```
"pyautogui>=0.9.54"
"opencv-python-headless>=4.9.0"
"Pillow>=10.0.0"
```

### New: `src/open_llm_vtuber/modules/vision_loop.py`

```python
"""Proactive screen watcher — pyautogui + pHash AFK detection."""
import threading, time, random, asyncio
from pathlib import Path
from typing import Callable
import cv2, numpy as np, pyautogui
from loguru import logger

class ScreenWatcher:
    def __init__(
        self,
        session_dir: Path,
        knowledge_base,           # KnowledgeBase instance
        trigger_callback: Callable[[str], None],
        event_loop: asyncio.AbstractEventLoop,
    ):
        self._session_dir = session_dir
        self._kb = knowledge_base
        self._trigger = trigger_callback
        self._loop = event_loop
        self._last_hash = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._hasher = cv2.img_hash.PHash_create()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop_body, daemon=True)
        self._thread.start()
        logger.info("ScreenWatcher started")

    def stop(self):
        self._running = False
        logger.info("ScreenWatcher stopped")

    def _take_screenshot(self) -> tuple[Path, np.ndarray]:
        ts = int(time.time())
        path = self._session_dir / "screenshots" / f"{ts}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        img = pyautogui.screenshot()
        img.save(str(path))
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return path, cv_img

    def _phash(self, img: np.ndarray) -> np.ndarray:
        return self._hasher.compute(img)

    def _hamming(self, h1, h2) -> float:
        return self._hasher.compare(h1, h2)

    def _loop_body(self):
        while self._running:
            time.sleep(random.uniform(15, 25))
            try:
                path, cv_img = self._take_screenshot()
                h = self._phash(cv_img)

                if self._last_hash is not None and self._hamming(self._last_hash, h) < 5:
                    logger.debug("ScreenWatcher: AFK (unchanged), skipping")
                    continue

                self._last_hash = h
                future = asyncio.run_coroutine_threadsafe(
                    self._kb.get_game_context("unknown", "current_screen", str(path)),
                    self._loop,
                )
                advice = future.result(timeout=90)
                if advice:
                    self._trigger(advice)
            except Exception as e:
                logger.error(f"ScreenWatcher error: {e}")
```

### Modify: `src/open_llm_vtuber/websocket_handler.py`

- Add `_screen_watchers: Dict[str, ScreenWatcher] = {}`
- On new connection: instantiate `ScreenWatcher`, call `.start()`; trigger_callback sends
  `{"type": "ai-speak-signal", "text": advice}` to the client's message queue
- On disconnect: call `_screen_watchers[client_uid].stop()`, pop from dict

### Phase 3 Test

```bash
# Open a game screenshot fullscreen on the display
uv run run_server.py --verbose
# → Connect browser client
# → After 15-25s: sessions/{uid}/screenshots/{ts}.png should appear
# → Logs show pHash comparison + ai-speak-signal trigger
```

---

## Phase 4: Supabase Memory + Player2

### New dependency (`pyproject.toml`)
```
"supabase>=2.3.0"
```

### Supabase SQL migration (run once in Supabase dashboard)

```sql
CREATE TABLE IF NOT EXISTS user_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    game_name TEXT,
    advice_given TEXT,
    user_reaction TEXT DEFAULT 'unknown',
    session_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    chat_history JSONB,
    chat_summary TEXT,
    session_id TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS long_term_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL UNIQUE,
    bot_id TEXT DEFAULT 'gameplay_companion',
    preferences_json JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### New: `src/open_llm_vtuber/integrations/__init__.py` (empty)

### New: `src/open_llm_vtuber/integrations/memory_manager.py`

```python
"""Supabase-backed per-user memory: history, chat logs, long-term profile."""
import os
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from supabase import create_client, Client

class MemoryManager:
    def __init__(self, user_id: str, bot_id: str = "gameplay_companion"):
        load_dotenv()
        self.client: Client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        self.user_id = user_id
        self.bot_id = bot_id

    async def save_advice(self, game_name: str, advice_given: str, session_id: str):
        self.client.table("user_history").insert({
            "user_id": self.user_id,
            "game_name": game_name,
            "advice_given": advice_given,
            "session_id": session_id,
        }).execute()

    async def get_long_term_profile(self) -> dict:
        res = (
            self.client.table("long_term_profile")
            .select("preferences_json")
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        return res.data["preferences_json"] if res.data else {}

    async def update_long_term_profile(self, preferences: dict):
        self.client.table("long_term_profile").upsert({
            "user_id": self.user_id,
            "bot_id": self.bot_id,
            "preferences_json": preferences,
            "updated_at": datetime.utcnow().isoformat(),
        }, on_conflict="user_id").execute()

    async def get_recent_history(self, limit: int = 5) -> list[dict]:
        res = (
            self.client.table("user_history")
            .select("game_name,advice_given,timestamp")
            .eq("user_id", self.user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    async def save_chat_log(self, chat_history: list, chat_summary: str, session_id: str):
        self.client.table("chat_logs").insert({
            "user_id": self.user_id,
            "chat_history": chat_history,
            "chat_summary": chat_summary,
            "session_id": session_id,
        }).execute()
```

### Modify: `src/open_llm_vtuber/service_context.py`

- Add `memory_manager: MemoryManager | None = None`
- In `load_cache()`: `self.memory_manager = MemoryManager(user_id=client_uid)`
- In `construct_system_prompt()`: fetch profile + recent history, prepend:
  ```
  [USER LONG-TERM PROFILE]: {profile_json}
  [RECENT GAME HISTORY (last 5)]: {history_text}
  ```

### Modify: `src/open_llm_vtuber/conversations/single_conversation.py`

After `full_response` assembled:
```python
if context.memory_manager and metadata.get("game_name"):
    await context.memory_manager.save_advice(
        metadata["game_name"], full_response, context.history_uid
    )
```

### Modify: `src/open_llm_vtuber/websocket_handler.py`

On disconnect:
```python
if context.memory_manager:
    history = context.agent_engine._memory if hasattr(context.agent_engine, "_memory") else []
    await context.memory_manager.save_chat_log(history, "", client_uid)
```

### Player2 Platform

**Research** → `docs/p2_platform_specs.md`

**New: `src/open_llm_vtuber/publishing/__init__.py`** (empty)

**New: `src/open_llm_vtuber/publishing/player2_platform.py`**
- `Player2Platform` class with manifest upload, capability registration
- Requires: `PLAYER2_API_KEY` env var (request from user)

**New: `src/open_llm_vtuber/publishing/generate_manifest.py`**
- Reads project metadata, generates `player2_manifest.json`

**New: `player2_manifest.json`** — full manifest per Player2 spec

### Phase 4 Test

```bash
# Check Supabase: user_history, chat_logs, long_term_profile tables populated
# Check verbose logs: system_prompt contains [USER LONG-TERM PROFILE]
# Send 2 messages about same game — verify advice saved per-message
```

---

## Phase 5: E2E Simulation

### New: `tests/__init__.py` (empty)

### New: `tests/simulation.py`

Test data (real screenshots downloaded to `tests/data/`):

| File | Game | State |
|------|------|-------|
| `elden1.jpg` | Elden Ring | Exploring open world |
| `elden2.jpg` | Elden Ring | Boss fight started |
| `elden3.jpg` | Elden Ring | Critical HP |
| `mc1.jpg` | Minecraft | Empty hotbar |
| `mc2.jpg` | Minecraft | Inventory chaos |
| `mc3.jpg` | Minecraft | Crafting table open |
| `fn1.jpg` | Fortnite | Early game landing |
| `fn2.jpg` | Fortnite | Storm closing in |
| `fn3.jpg` | Fortnite | Final circle |
| `val1.jpg` | Valorant | Pistol round |
| `val2.jpg` | Valorant | Eco round |
| `val3.jpg` | Valorant | Spike plant |

Assertions per game scenario (60-second loop):
1. `game_name` correctly identified in Qdrant payload
2. Research mode triggered on first call (Qdrant was empty)
3. Qdrant has ≥1 new vector after research
4. `user_history` has new row with `advice_given`
5. Second call with same state hits Qdrant (score ≥ 0.8, no subprocess re-run)

---

## Phase Report Template

Each phase creates `Phase_X_Report.md`:

```markdown
# Phase X Report

## Timestamps
- Start: YYYY-MM-DD HH:MM
- End: YYYY-MM-DD HH:MM
- Duration: N minutes

## Completed
- [ ] item 1
- [ ] item 2

## Test Results
- Server starts: ✅/❌
- Core functionality: ✅/❌
- Previous phase tests still pass: ✅/❌

## Issues & Resolutions
- Issue: ...
  Resolution: ...

## Questions for User
- ...
```
