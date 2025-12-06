# Acore Bot Comprehensive Improvement Plan

**Generated**: 2025-12-02
**Approach**: Balanced (Features + Fixes + Optimizations)
**Pain Points**: Slow startup, Memory issues, Response latency, Hard to maintain
**Risk Tolerance**: Aggressive refactoring approved

---

## Executive Summary

This plan addresses critical issues across 377,545 lines of code in the acore_bot codebase through 5 phased approaches:

1. **Phase 1 (Critical Stability)**: Fix blocking operations, memory leaks, error handling (~1-2 weeks)
2. **Phase 2 (Performance Foundations)**: Implement caching, async HTTP, rate limiting (~2-3 weeks)
3. **Phase 3 (Architecture Refactoring)**: Split massive files, add testing, create interfaces (~3-4 weeks)
4. **Phase 4 (Advanced Optimizations)**: Advanced caching, memory optimization (~2 weeks)
5. **Phase 5 (New Features)**: Leverage improved architecture for new capabilities (~2-3 weeks)

**Total Estimated Timeline**: 10-14 weeks for complete implementation

---

## Phase 1: Critical Stability Fixes (Week 1-2)

### Objective
Address immediate pain points causing slow startup, crashes, and unreliable behavior.

### Tasks

#### 1.1 Fix Blocking Model Downloads (Priority: CRITICAL)
**Problem**: Bot startup hangs for 5+ minutes downloading 311MB models
**Files**:
- `/root/acore_bot/services/kokoro_tts.py:38-89`
- `/root/acore_bot/main.py:163` (initialization)

**Implementation**:
```python
# Change from blocking download in __init__ to lazy loading
class KokoroTTSService:
    def __init__(self):
        self._model_ready = asyncio.Event()
        self._model = None

    async def _lazy_load_model(self):
        # Download in background task
        if not self._model:
            self._model = await asyncio.to_thread(self._download_model)
            self._model_ready.set()

    async def generate(self, text):
        await self._model_ready.wait()  # Wait for model if needed
        # ... rest of generation
```

**Breaking Changes**: None (backward compatible)
**Testing**: Verify startup time < 30 seconds, model downloads in background
**Complexity**: 4-6 hours

#### 1.2 Fix Bare Exception Handlers (Priority: HIGH)
**Problem**: 8+ bare `except:` clauses mask critical errors
**Files**:
- `/root/acore_bot/cogs/chat.py:663`
- `/root/acore_bot/services/kokoro_api_client.py:58,62`
- `/root/acore_bot/services/naturalness.py:434`

**Implementation**:
```python
# Change from:
try:
    result = await some_operation()
except:  # BAD
    pass

# To:
try:
    result = await some_operation()
except (SpecificError1, SpecificError2) as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    # Handle gracefully
```

**Breaking Changes**: May expose previously hidden errors (good!)
**Testing**: Run bot for 24h, verify no unhandled exceptions
**Complexity**: 3-4 hours

#### 1.3 Fix Memory Leaks (Priority: CRITICAL)
**Problem**: Unbounded sets/dicts cause memory growth over days

##### 1.3.1 Metrics Service Active Stats
**File**: `/root/acore_bot/services/metrics.py:36-88`

**Implementation**:
```python
class MetricsService:
    def __init__(self):
        self.active_users = set()  # Currently unbounded
        self._last_reset = datetime.now()

    async def _hourly_reset_task(self):
        while True:
            await asyncio.sleep(3600)
            self.active_users.clear()
            self.active_channels.clear()
            self._last_reset = datetime.now()
```

**Complexity**: 2 hours

##### 1.3.2 Ambient Mode Channel States
**File**: `/root/acore_bot/services/ambient_mode.py:21,45`

**Implementation**:
```python
from collections import OrderedDict

class AmbientMode:
    def __init__(self):
        self.channel_states = OrderedDict()  # LRU with max size
        self.max_channels = 500

    def _get_or_create_state(self, channel_id):
        if channel_id not in self.channel_states:
            if len(self.channel_states) >= self.max_channels:
                self.channel_states.popitem(last=False)  # Remove oldest
        state = self.channel_states.pop(channel_id, ChannelState())
        self.channel_states[channel_id] = state  # Move to end
        return state
```

**Complexity**: 3 hours

##### 1.3.3 Voice Clients Cleanup
**File**: `/root/acore_bot/cogs/voice.py:49`

**Implementation**:
```python
# Add event listener
@commands.Cog.listener()
async def on_guild_remove(self, guild):
    if guild.id in self.voice_clients:
        del self.voice_clients[guild.id]
        logger.info(f"Cleaned up voice client for removed guild {guild.id}")
```

**Complexity**: 1 hour

**Total Memory Leak Fixes**: 6 hours

#### 1.4 Remove Dead Code (Priority: MEDIUM)
**Problem**: 671 lines of deprecated code causing confusion

**Files to Delete**:
- `/root/acore_bot/services/deprecated/rvc_webui.py` (190 lines)
- `/root/acore_bot/services/deprecated/rvc.py` (242 lines)
- `/root/acore_bot/services/deprecated/rvc_webui_gradio.py` (239 lines)

**Also Clean**:
- `/root/acore_bot/cogs/chat.py:19-22` - Remove commented StreamingTTS
- `/root/acore_bot/cogs/voice.py:17-18` - Remove commented sound effects

**Breaking Changes**: None (already deprecated)
**Testing**: Ensure no imports reference these files
**Complexity**: 1 hour

#### 1.5 Fix Missing Imports (Priority: HIGH)
**Problem**: chat.py:133 uses `datetime` type hint but imports conditionally

**File**: `/root/acore_bot/cogs/chat.py:133,605`

**Implementation**:
```python
# Move to top of file
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Remove conditional import at line 605
```

**Breaking Changes**: None
**Testing**: Run type checker (`mypy`)
**Complexity**: 30 minutes

### Phase 1 Deliverables
- [ ] Bot startup time reduced from 5+ minutes to <30 seconds
- [ ] All bare except clauses fixed with specific error handling
- [ ] Memory usage stable over 7+ day runs (no unbounded growth)
- [ ] 671 lines of dead code removed
- [ ] All type hints valid

**Total Phase 1 Time**: 15-20 hours (1-2 weeks at part-time pace)

---

## Phase 2: Performance Foundations (Week 3-5)

### Objective
Eliminate performance bottlenecks through caching, async operations, and rate limiting.

### Tasks

#### 2.1 Implement LLM Response Caching (Priority: CRITICAL)
**Problem**: Duplicate queries cause redundant API calls, adding 2-10s latency each

**Files**:
- `/root/acore_bot/services/ollama.py`
- `/root/acore_bot/services/openrouter.py`

**Implementation**:
```python
from functools import lru_cache
import hashlib

class OllamaService:
    def __init__(self):
        self._response_cache = {}  # {query_hash: (response, timestamp)}
        self._cache_ttl = 300  # 5 minutes

    async def generate_response(self, messages, **kwargs):
        # Create cache key from messages + model + temp
        cache_key = hashlib.sha256(
            f"{messages}{self.model}{kwargs.get('temperature', 0.7)}".encode()
        ).hexdigest()

        # Check cache
        if cache_key in self._response_cache:
            response, timestamp = self._response_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for query")
                return response

        # Generate and cache
        response = await self._generate(messages, **kwargs)
        self._response_cache[cache_key] = (response, time.time())

        # Evict old entries (keep cache under 1000 entries)
        if len(self._response_cache) > 1000:
            self._evict_old_entries()

        return response
```

**Configuration**:
```python
# config.py
LLM_CACHE_ENABLED = os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"
LLM_CACHE_TTL = int(os.getenv("LLM_CACHE_TTL", "300"))  # 5 minutes
LLM_CACHE_MAX_SIZE = int(os.getenv("LLM_CACHE_MAX_SIZE", "1000"))
```

**Breaking Changes**: None
**Testing**: Verify duplicate questions return cached responses (check logs)
**Expected Impact**: 50-80% reduction in LLM API calls for common queries
**Complexity**: 6-8 hours

#### 2.2 Replace Synchronous HTTP with Async (Priority: CRITICAL)
**Problem**: RVC HTTP client blocks event loop, causing 10-30s hangs

**File**: `/root/acore_bot/services/rvc_http.py:27-150`

**Implementation**:
```python
# Replace requests with aiohttp
import aiohttp

class RVCHTTPService:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = config.RVC_WEBUI_URL

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=300)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def convert_voice(self, audio_path: str, model_name: str) -> bytes:
        await self._ensure_session()

        # Async multipart upload
        async with self.session.post(
            f"{self.base_url}/infer",
            data={"model": model_name},
            files={"audio": open(audio_path, "rb")}
        ) as response:
            response.raise_for_status()
            return await response.read()

    async def close(self):
        if self.session:
            await self.session.close()
```

**Breaking Changes**: None (API compatible)
**Testing**: RVC conversion still works, measure response time improvement
**Expected Impact**: 30-50% faster RVC operations, no event loop blocking
**Complexity**: 4-6 hours

#### 2.3 Implement Rate Limiting Infrastructure (Priority: HIGH)
**Problem**: No protection against API quota exhaustion or IP bans

##### 2.3.1 LLM Rate Limiter
**Files**: `/root/acore_bot/services/ollama.py`, `/root/acore_bot/services/openrouter.py`

**Implementation**:
```python
class RateLimiter:
    def __init__(self, max_concurrent: int = 5, requests_per_minute: int = 60):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.requests = []  # List of timestamps
        self.rpm_limit = requests_per_minute

    async def acquire(self):
        async with self.semaphore:
            # Check rate limit
            now = time.time()
            self.requests = [t for t in self.requests if now - t < 60]

            if len(self.requests) >= self.rpm_limit:
                wait_time = 60 - (now - self.requests[0])
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

            self.requests.append(now)
            yield

# Usage
class OpenRouterService:
    def __init__(self):
        self.rate_limiter = RateLimiter(max_concurrent=3, requests_per_minute=20)

    async def generate_response(self, messages):
        async with self.rate_limiter.acquire():
            return await self._generate(messages)
```

**Complexity**: 4 hours

##### 2.3.2 Web Search Rate Limiter
**File**: `/root/acore_bot/services/web_search.py:43-151`

**Implementation**:
```python
class WebSearchService:
    def __init__(self):
        self.last_request_time = 0
        self.min_delay = 2.0  # 2 seconds between requests

    async def search(self, query: str):
        # Enforce minimum delay
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            await asyncio.sleep(self.min_delay - elapsed)

        self.last_request_time = time.time()
        return await self._search(query)
```

**Complexity**: 2 hours

**Total Rate Limiting**: 6 hours

#### 2.4 Cache RAG Query Embeddings (Priority: HIGH)
**Problem**: Embeddings recomputed every query, adding 500ms-2s latency

**File**: `/root/acore_bot/services/rag.py:261-280`

**Implementation**:
```python
from functools import lru_cache

class RAGService:
    def __init__(self):
        self.embedding_cache = {}
        self.cache_max_size = 500

    async def _get_embedding(self, text: str):
        if text in self.embedding_cache:
            return self.embedding_cache[text]

        embedding = await asyncio.to_thread(
            self.embedding_model.encode, [text]
        )

        self.embedding_cache[text] = embedding

        # LRU eviction
        if len(self.embedding_cache) > self.cache_max_size:
            oldest = next(iter(self.embedding_cache))
            del self.embedding_cache[oldest]

        return embedding

    async def search(self, query: str, top_k: int = 5):
        query_embedding = await self._get_embedding(query)
        # ... rest of search logic
```

**Breaking Changes**: None
**Testing**: Verify search results unchanged, measure latency reduction
**Expected Impact**: 70-90% faster repeat searches
**Complexity**: 3-4 hours

#### 2.5 Optimize Profile Index Loading (Priority: HIGH)
**Problem**: 5-second startup delay rebuilding indices for 1000+ users

**File**: `/root/acore_bot/services/user_profiles.py:115-141`

**Implementation**:
```python
import pickle

class UserProfileService:
    INDEX_CACHE_FILE = "data/user_profiles/_index_cache.pkl"

    async def _load_or_build_indices(self):
        # Try to load cached indices
        if os.path.exists(self.INDEX_CACHE_FILE):
            try:
                with open(self.INDEX_CACHE_FILE, "rb") as f:
                    cache_data = pickle.load(f)
                    if cache_data["version"] == self.INDEX_VERSION:
                        self.trait_index = cache_data["trait_index"]
                        self.interest_index = cache_data["interest_index"]
                        logger.info("Loaded profile indices from cache")
                        return
            except Exception as e:
                logger.warning(f"Failed to load index cache: {e}")

        # Build indices from scratch
        await self._build_indices()

        # Save to cache
        await self._save_index_cache()

    async def _save_index_cache(self):
        cache_data = {
            "version": self.INDEX_VERSION,
            "trait_index": self.trait_index,
            "interest_index": self.interest_index,
            "timestamp": time.time()
        }
        await asyncio.to_thread(
            lambda: pickle.dump(cache_data, open(self.INDEX_CACHE_FILE, "wb"))
        )
```

**Breaking Changes**: None
**Testing**: Verify profile lookups work, measure startup improvement
**Expected Impact**: Startup time reduced by 4-5 seconds
**Complexity**: 3 hours

#### 2.6 Parallelize Profile Saves (Priority: MEDIUM)
**Problem**: 100 dirty profiles = 100 sequential file writes

**File**: `/root/acore_bot/services/user_profiles.py:74-95`

**Implementation**:
```python
async def _flush_dirty_profiles(self):
    dirty_ids = list(self.dirty_profiles)
    self.dirty_profiles.clear()

    # Parallel save with concurrency limit
    semaphore = asyncio.Semaphore(10)

    async def save_with_limit(user_id):
        async with semaphore:
            await self._flush_profile(user_id)

    await asyncio.gather(
        *[save_with_limit(uid) for uid in dirty_ids],
        return_exceptions=True
    )
```

**Breaking Changes**: None
**Testing**: Verify all profiles saved correctly
**Expected Impact**: 10x faster bulk saves
**Complexity**: 2 hours

### Phase 2 Deliverables
- [ ] LLM response caching reduces API calls by 50-80%
- [ ] RVC operations non-blocking (async HTTP)
- [ ] Rate limiting prevents API quota issues
- [ ] RAG searches 70-90% faster for repeat queries
- [ ] Bot startup <10 seconds with cached indices
- [ ] Profile saves 10x faster

**Total Phase 2 Time**: 28-35 hours (2-3 weeks)

---

## Phase 3: Architecture Refactoring (Week 6-9)

### Objective
Make codebase maintainable through modularization, testing, and clean interfaces.

### Tasks

#### 3.1 Split Massive chat.py (2,237 lines) (Priority: CRITICAL)
**Problem**: Single file handles 21 commands, impossible to test or modify safely

**File**: `/root/acore_bot/cogs/chat.py`

**New Structure**:
```
cogs/
├── chat/
│   ├── __init__.py           # Main ChatCog
│   ├── commands.py           # /chat, /ask commands
│   ├── image_analysis.py     # Image handling
│   ├── history_manager.py    # Conversation history
│   ├── response_handler.py   # Response generation
│   └── implicit_chat.py      # Mention handling
```

**Implementation Steps**:
1. Create new `cogs/chat/` package
2. Extract image analysis logic (lines 400-600) → `image_analysis.py`
3. Extract history management (lines 150-250) → `history_manager.py`
4. Extract response generation (lines 650-950) → `response_handler.py`
5. Extract implicit chat (lines 1100-1300) → `implicit_chat.py`
6. Main ChatCog orchestrates these modules

**Breaking Changes**: None (internal refactor)
**Testing**: All chat commands still work identically
**Complexity**: 16-20 hours

#### 3.2 Extract Web Dashboard HTML (Priority: MEDIUM)
**Problem**: 1400+ lines of HTML embedded as strings

**File**: `/root/acore_bot/services/web_dashboard.py:600-2000`

**New Structure**:
```
templates/
├── dashboard.html
├── metrics.html
└── components/
    ├── status_card.html
    ├── metrics_chart.html
    └── service_list.html
```

**Implementation**:
```python
from jinja2 import Environment, FileSystemLoader

class WebDashboard:
    def __init__(self):
        self.template_env = Environment(
            loader=FileSystemLoader("templates")
        )

    async def render_dashboard(self):
        template = self.template_env.get_template("dashboard.html")
        return template.render(
            bot_status=self.bot.status,
            metrics=self.metrics_service.get_stats()
        )
```

**Breaking Changes**: None
**Testing**: Dashboard renders identically
**Complexity**: 8-10 hours

#### 3.3 Create Service Interface Abstractions (Priority: HIGH)
**Problem**: Tight coupling makes swapping implementations impossible

**New Files**:
```
services/
├── interfaces/
│   ├── __init__.py
│   ├── tts_interface.py      # Abstract TTS base
│   ├── stt_interface.py      # Abstract STT base
│   ├── llm_interface.py      # Abstract LLM base
│   └── rvc_interface.py      # Abstract RVC base
```

**Implementation**:
```python
# services/interfaces/tts_interface.py
from abc import ABC, abstractmethod

class TTSInterface(ABC):
    @abstractmethod
    async def generate(self, text: str, voice: str) -> bytes:
        """Generate TTS audio from text"""
        pass

    @abstractmethod
    async def list_voices(self) -> list[str]:
        """List available voices"""
        pass

# services/kokoro_tts.py
class KokoroTTSService(TTSInterface):
    async def generate(self, text: str, voice: str) -> bytes:
        # Implementation
        pass
```

**Benefits**:
- Easy to add new TTS engines
- Can mock for testing
- Clear contracts between components

**Breaking Changes**: Minimal (update instantiation)
**Complexity**: 12-16 hours

#### 3.4 Implement Comprehensive Test Suite (Priority: CRITICAL)
**Problem**: 0.04% test coverage makes refactoring risky

**Structure**:
```
tests/
├── unit/
│   ├── services/
│   │   ├── test_ollama.py
│   │   ├── test_user_profiles.py
│   │   ├── test_rag.py
│   │   └── test_metrics.py
│   └── utils/
│       └── test_helpers.py
├── integration/
│   ├── test_chat_flow.py
│   ├── test_voice_pipeline.py
│   └── test_ambient_mode.py
└── conftest.py  # Pytest fixtures
```

**Priority Tests**:
1. **Unit tests for services** (20 tests minimum):
   - OllamaService.generate_response()
   - UserProfileService.update_profile()
   - RAGService.search()
   - MetricsService tracking
   - ChatHistoryManager cache operations

2. **Integration tests** (10 tests):
   - Full chat command flow
   - TTS → RVC pipeline
   - Ambient mode triggers

**Setup**:
```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.fixture
def mock_bot():
    bot = Mock()
    bot.user = Mock(id=123, name="TestBot")
    return bot

@pytest.fixture
async def ollama_service():
    service = OllamaService()
    service.client = AsyncMock()
    return service

# tests/unit/services/test_ollama.py
import pytest

@pytest.mark.asyncio
async def test_response_caching(ollama_service):
    # First call
    response1 = await ollama_service.generate_response([{"role": "user", "content": "Hello"}])

    # Second identical call should hit cache
    response2 = await ollama_service.generate_response([{"role": "user", "content": "Hello"}])

    assert response1 == response2
    assert ollama_service.client.post.call_count == 1  # Only called once
```

**Testing Tools**:
- pytest + pytest-asyncio
- pytest-cov for coverage
- pytest-mock for mocking

**Target Coverage**: 60% by end of phase

**Breaking Changes**: None
**Complexity**: 24-30 hours

#### 3.5 Implement Dependency Injection (Priority: MEDIUM)
**Problem**: Services created globally, hard to test and configure

**Current** (main.py):
```python
tts_service = TTSService()
rvc_service = RVCUnifiedService()
```

**New Approach**:
```python
# services/service_container.py
class ServiceContainer:
    def __init__(self, config):
        self.config = config
        self._services = {}

    def get_tts(self) -> TTSInterface:
        if "tts" not in self._services:
            engine = self.config.TTS_ENGINE
            if engine == "kokoro":
                self._services["tts"] = KokoroTTSService(self.config)
            elif engine == "supertonic":
                self._services["tts"] = SupertonicTTSService(self.config)
            else:
                self._services["tts"] = EdgeTTSService(self.config)
        return self._services["tts"]

    # ... similar for other services

# main.py
container = ServiceContainer(config)
bot = OllamaBot(container=container)

# cogs/voice.py
class VoiceCog(commands.Cog):
    def __init__(self, bot, container):
        self.bot = bot
        self.tts = container.get_tts()
        self.rvc = container.get_rvc()
```

**Benefits**:
- Easy to swap implementations
- Simple to inject mocks for testing
- Centralized service lifecycle management

**Breaking Changes**: Refactor cog initialization
**Complexity**: 10-12 hours

### Phase 3 Deliverables
- [ ] chat.py split into 6 modular files
- [ ] Web dashboard uses Jinja2 templates
- [ ] Service interfaces defined for TTS/STT/LLM/RVC
- [ ] 30+ unit tests with 60% code coverage
- [ ] Dependency injection container implemented
- [ ] All existing functionality works identically

**Total Phase 3 Time**: 70-88 hours (3-4 weeks)

---

## Phase 4: Advanced Optimizations (Week 10-11)

### Objective
Push performance further with advanced techniques.

### Tasks

#### 4.1 Implement Request Deduplication (Priority: MEDIUM)
**Problem**: Multiple users asking same question simultaneously causes duplicate LLM calls

**Implementation**:
```python
class RequestDeduplicator:
    def __init__(self):
        self.pending_requests = {}  # {request_hash: Future}

    async def deduplicate(self, key: str, coro):
        if key in self.pending_requests:
            logger.debug(f"Deduplicating request: {key}")
            return await self.pending_requests[key]

        # Create future for this request
        future = asyncio.create_task(coro)
        self.pending_requests[key] = future

        try:
            result = await future
            return result
        finally:
            # Cleanup after short delay
            await asyncio.sleep(5)
            self.pending_requests.pop(key, None)

# Usage in OllamaService
class OllamaService:
    def __init__(self):
        self.deduplicator = RequestDeduplicator()

    async def generate_response(self, messages):
        key = self._hash_request(messages)
        return await self.deduplicator.deduplicate(
            key, self._generate(messages)
        )
```

**Expected Impact**: 20-30% reduction in LLM calls during high traffic
**Complexity**: 6 hours

#### 4.2 Optimize ChatHistoryManager LRU (Priority: MEDIUM)
**Problem**: O(n) list operations slow down with 100+ cached channels

**File**: `/root/acore_bot/utils/helpers.py:48-66`

**Implementation**:
```python
from collections import OrderedDict

class ChatHistoryManager:
    def __init__(self, max_cache_size: int = 100):
        self._cache = OrderedDict()
        self.max_cache_size = max_cache_size

    async def get_history(self, channel_id: int):
        if channel_id in self._cache:
            # Move to end (most recent)
            self._cache.move_to_end(channel_id)
            return self._cache[channel_id]

        # Load from disk
        history = await self._load_from_disk(channel_id)

        # Add to cache
        self._cache[channel_id] = history

        # Evict if needed
        if len(self._cache) > self.max_cache_size:
            oldest_id, _ = self._cache.popitem(last=False)
            logger.debug(f"Evicted channel {oldest_id} from cache")

        return history
```

**Expected Impact**: 10x faster cache operations with large cache
**Complexity**: 3 hours

#### 4.3 Implement Metrics Batch Logging (Priority: LOW)
**Problem**: 100 voice commands = 100+ individual log writes

**File**: `/root/acore_bot/services/metrics.py`

**Implementation**:
```python
class MetricsService:
    def __init__(self):
        self.pending_metrics = []
        self.batch_size = 50
        self.batch_interval = 60  # seconds

    async def log_event(self, event_type: str, data: dict):
        self.pending_metrics.append({
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        })

        if len(self.pending_metrics) >= self.batch_size:
            await self._flush_metrics()

    async def _metrics_batch_task(self):
        while True:
            await asyncio.sleep(self.batch_interval)
            await self._flush_metrics()

    async def _flush_metrics(self):
        if not self.pending_metrics:
            return

        batch = self.pending_metrics[:]
        self.pending_metrics.clear()

        # Write all metrics in one operation
        await self._write_batch_to_disk(batch)
```

**Expected Impact**: 90% reduction in disk I/O for metrics
**Complexity**: 4 hours

#### 4.4 Profile-Guided Optimization (Priority: LOW)
**Use profiling to identify real bottlenecks**

**Tools**:
- `py-spy` for production profiling
- `cProfile` for detailed analysis
- `memory_profiler` for memory analysis

**Process**:
1. Run bot under load with py-spy for 1 hour
2. Analyze flamegraph to identify hot paths
3. Optimize top 3 bottlenecks
4. Re-profile and verify improvements

**Complexity**: 8-10 hours

### Phase 4 Deliverables
- [x] Request deduplication reduces LLM calls by 20-30%
- [x] ChatHistoryManager 10x faster with OrderedDict
- [x] Metrics batch logging reduces I/O by 90%
- [x] Profile-guided optimization tools and guide created

**Total Phase 4 Time**: 21-27 hours (2 weeks)

**Completed**: 2025-12-05

---

## Phase 5: New Features (Week 12-14)

### Objective
Leverage improved architecture to add high-value features.

### Proposed Features

#### 5.1 Multi-Model LLM Routing (Complexity: 8h)
**Description**: Automatically route simple queries to fast models, complex to powerful models

**Implementation**:
```python
class LLMRouter:
    def __init__(self, container):
        self.simple_model = container.get_llm("llama3.2:3b")  # Fast
        self.complex_model = container.get_llm("qwen2.5:32b")  # Smart

    async def route_and_generate(self, messages):
        complexity = await self._estimate_complexity(messages)

        if complexity < 0.3:
            return await self.simple_model.generate(messages)
        else:
            return await self.complex_model.generate(messages)

    async def _estimate_complexity(self, messages):
        # Use lightweight model to score query complexity
        prompt = f"Rate complexity 0-1: {messages[-1]['content']}"
        # Quick LLM call with cached prompt
```

**Benefits**: 50-70% cost reduction, faster responses for simple queries

#### 5.2 Voice Activity Detection (VAD) Improvements (Complexity: 12h)
**Description**: Replace simple threshold with ML-based VAD for better voice detection

**Implementation**:
- Use `webrtcvad` or `silero-vad` for real-time voice detection
- Reduces false triggers from background noise
- Better conversation flow in voice channels

**Benefits**: 80% fewer false triggers, more natural voice interaction

#### 5.3 Conversation Summarization with Callbacks (Complexity: 10h)
**Description**: Automatically summarize long conversations and surface key points later

**Implementation**:
```python
class ConversationSummarizer:
    async def summarize_and_schedule_callback(self, channel_id):
        # Get last 100 messages
        messages = await self.history.get_recent(channel_id, 100)

        # Generate summary
        summary = await self.llm.generate([
            {"role": "system", "content": "Summarize key discussion points"},
            {"role": "user", "content": str(messages)}
        ])

        # Extract action items
        action_items = await self._extract_action_items(summary)

        # Schedule follow-up callback
        for item in action_items:
            await self.callback_system.schedule(
                channel_id,
                item["when"],
                f"Remember to: {item['what']}"
            )
```

**Benefits**: Better long-term memory, proactive follow-ups

#### 5.4 Dynamic Persona Switching Based on Context (Complexity: 10h)
**Description**: Automatically adjust persona based on conversation topic/mood

**Implementation**:
```python
class ContextualPersonaManager:
    async def get_optimal_persona(self, channel_id, messages):
        # Analyze recent conversation
        topics = await self._extract_topics(messages)
        mood = await self._detect_mood(messages)

        # Choose persona
        if "gaming" in topics:
            return "chief"  # Gaming-focused
        elif mood == "serious":
            return "assistant"  # Professional
        elif mood == "playful":
            return "gothmommy"  # Fun
        else:
            return self.default_persona
```

**Benefits**: More appropriate responses for context

#### 5.5 Advanced RAG with Source Attribution (Complexity: 12h)
**Description**: Show users which documents RAG retrieved from

**Implementation**:
```python
class EnhancedRAGService:
    async def search_with_sources(self, query: str):
        results = await self.search(query, top_k=3)

        response = {
            "context": results["text"],
            "sources": [
                {
                    "file": r["metadata"]["source"],
                    "relevance": r["score"],
                    "excerpt": r["text"][:200]
                }
                for r in results["documents"]
            ]
        }
        return response

# In chat response
async def handle_chat(ctx, message):
    rag_results = await bot.rag.search_with_sources(message)

    response = await bot.llm.generate(messages, context=rag_results["context"])

    # Include sources in embed
    embed = discord.Embed(title="Sources")
    for source in rag_results["sources"]:
        embed.add_field(name=source["file"], value=source["excerpt"])

    await ctx.send(response, embed=embed)
```

**Benefits**: Transparency, easier fact-checking, builds trust

#### 5.6 Voice Cloning Pipeline (Complexity: 16h)
**Description**: Let users train custom RVC models from voice samples

**Implementation**:
- Record 5-10 minutes of user voice
- Submit to RVC training pipeline (background job)
- Auto-generate voice model
- Add to available voices

**Benefits**: Highly personalized voice interactions

#### 5.7 Metrics Dashboard API (Complexity: 6h)
**Description**: REST API for external monitoring tools

**Implementation**:
```python
# New endpoint in web_dashboard.py
@app.route("/api/metrics")
async def metrics_api():
    return jsonify({
        "response_times": list(metrics.response_times),
        "active_users": len(metrics.active_users),
        "cache_hit_rate": metrics.cache_hits / metrics.total_requests,
        "memory_usage_mb": get_memory_usage(),
        "uptime_seconds": time.time() - bot.start_time
    })
```

**Benefits**: Prometheus/Grafana integration, better ops visibility

### Phase 5 Deliverables
- [ ] Multi-model routing saves 50-70% on LLM costs
- [ ] VAD improvements reduce false triggers by 80%
- [ ] Conversation summarization with proactive callbacks
- [ ] Context-aware persona switching
- [ ] RAG with source attribution
- [ ] Voice cloning pipeline (optional)
- [ ] Metrics API for external tools

**Total Phase 5 Time**: 52-74 hours (2-3 weeks)

---

## Implementation Strategy

### Recommended Approach

**Week-by-Week**:
1. **Weeks 1-2**: Phase 1 (Critical Fixes) - Stabilize foundation
2. **Weeks 3-5**: Phase 2 (Performance) - Address latency/memory
3. **Weeks 6-9**: Phase 3 (Architecture) - Enable maintainability
4. **Weeks 10-11**: Phase 4 (Advanced Opt) - Polish performance
5. **Weeks 12-14**: Phase 5 (Features) - Deliver value

### Success Metrics

**Phase 1**:
- ✅ Startup time < 30s
- ✅ No memory growth over 7 days
- ✅ Zero bare except clauses

**Phase 2**:
- ✅ LLM API calls reduced 50%+
- ✅ RAG searches <500ms (was 2s+)
- ✅ No event loop blocking

**Phase 3**:
- ✅ 60% test coverage
- ✅ All files <500 lines
- ✅ CI/CD pipeline passing

**Phase 4**:
- ✅ 95th percentile response time <2s
- ✅ Memory usage <1GB for 100 users
- ✅ Zero crashes over 30 days

**Phase 5**:
- ✅ 5+ new features shipped
- ✅ User satisfaction improved (survey)

### Risk Mitigation

**Risks**:
1. **Breaking existing functionality** → Comprehensive testing before merging
2. **Users notice downtime** → Deploy in off-peak hours, staged rollout
3. **Performance regressions** → Benchmark before/after each phase
4. **Scope creep** → Stick to phased plan, defer new requests to Phase 6

### Rollback Plan

Each phase should be:
1. Developed in feature branch
2. Tested in staging environment
3. Deployed with feature flags
4. Monitored for 48h
5. Rolled back if issues detected

---

## Conclusion

This plan addresses all identified pain points:
- ✅ **Slow startup**: Fixed in Phase 1 (lazy loading) + Phase 2 (cached indices)
- ✅ **Memory issues**: Fixed in Phase 1 (leak fixes) + Phase 4 (optimizations)
- ✅ **Response latency**: Fixed in Phase 2 (caching, async) + Phase 4 (dedup, profiling)
- ✅ **Hard to maintain**: Fixed in Phase 3 (split files, tests, interfaces)

**Total Estimated Effort**: 186-254 hours (10-14 weeks at 20h/week)

**Next Steps**:
1. Review and approve plan
2. Set up development environment
3. Create Phase 1 feature branch
4. Begin implementation

Questions or adjustments needed before proceeding?
