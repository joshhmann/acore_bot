# Service Layer Documentation

This document provides comprehensive documentation of all service layers in the acore_bot project. Services are organized by domain and provide the core business logic for the bot.

**File**: `/root/acore_bot/services/`

---

## Table of Contents

1. [Service Organization](#service-organization)
2. [Service Interfaces](#service-interfaces)
3. [Core Services](#core-services)
4. [LLM Services](#llm-services)
5. [Memory Services](#memory-services)
6. [Voice Services](#voice-services)
7. [Persona Services](#persona-services)
8. [Discord Services](#discord-services)
9. [Service Factory](#service-factory)
10. [Integration Patterns](#integration-patterns)

---

## Service Organization

Services are organized into domain-based directories:

```
services/
├── __init__.py              # Service package initialization
├── core/                    # Core infrastructure services
├── llm/                     # LLM provider integrations
├── memory/                  # Memory and data management
├── voice/                   # TTS, STT, RVC services
├── persona/                 # AI personality system
├── discord/                 # Discord-specific features
├── analytics/               # Real-time dashboard and metrics (NEW)
├── interfaces/              # Service interface definitions
├── clients/                 # External API clients
└── deprecated/              # Legacy code
```

**File**: `/root/acore_bot/services/__init__.py` (Lines 1-10)

---

## Service Interfaces

All services follow interface-based design for consistency and swappability.

### LLMInterface

**File**: `/root/acore_bot/services/interfaces/llm_interface.py`

Abstract base class for all LLM providers.

**Key Methods**:
- `chat(messages, system_prompt, temperature, max_tokens)` - Send chat request
- `chat_stream(messages, ...)` - Stream responses token by token
- `generate(prompt, system_prompt)` - Simple prompt completion
- `chat_with_vision(prompt, images)` - Vision model support (optional)
- `is_available()` - Health check
- `initialize()` / `cleanup()` - Lifecycle management

**Interface Design** (Lines 7-163):
- Enforces consistent API across Ollama, OpenRouter, and future providers
- Supports both streaming and non-streaming responses
- Optional vision capabilities with NotImplementedError fallback
- Configurable sampling parameters (temperature, top_p, top_k, etc.)

### TTSInterface

**File**: `/root/acore_bot/services/interfaces/tts_interface.py`

Abstract base class for Text-to-Speech engines.

**Key Methods** (Lines 15-77):
- `generate(text, output_path, voice, speed)` - Generate speech from text
- `list_voices()` - List available voices
- `is_available()` - Service health check
- `cleanup()` - Resource cleanup

**Supports**:
- Multiple TTS engines (Kokoro, Supertonic, Edge)
- Voice selection and speed control
- Implementation-specific parameters via kwargs

### Other Interfaces

**File**: `/root/acore_bot/services/interfaces/` directory

- **STTInterface** - Speech-to-Text service interface
- **RVCInterface** - Voice conversion interface

---

## Core Services

Core infrastructure services that support the entire bot.

### ServiceFactory

**File**: `/root/acore_bot/services/core/factory.py`

Central factory for initializing and managing all services with dependency injection.

**Architecture** (Lines 41-273):
```python
class ServiceFactory:
    def __init__(self, bot):
        self.bot = bot
        self.services = {}

    def create_services(self):
        # Initialize in dependency order:
        # 1. Metrics (Core)
        # 2. LLM Services
        # 3. Audio Services (TTS, RVC, STT)
        # 4. Data Services (History, Profiles, RAG, Memory)
        # 5. Feature Services (Search, Reminders, Notes)
        # 6. AI/Persona Systems
        return self.services
```

**Initialization Order** (Lines 48-70):
1. **Metrics** - Performance tracking
2. **LLM** - Primary LLM provider (Ollama/OpenRouter)
3. **LLM Fallback** - Backup model chain
4. **Thinking** - Cheap/fast LLM for decisions
5. **Audio** - TTS, RVC, STT, Voice Listener
6. **Data** - History, Profiles, RAG, Memory Manager
7. **Features** - Web Search, Reminders, Notes, Conversation Manager
8. **AI Systems** - Persona, Tools, Relationships

**Key Features**:
- Conditional service initialization based on config
- Dependency injection pattern
- Centralized configuration management
- Service caching in dictionary

### MetricsService

**File**: `/root/acore_bot/services/core/metrics.py`

Comprehensive metrics and analytics tracking.

**Tracked Metrics** (Lines 15-720):

1. **Response Times** (Lines 108-155)
   - Rolling window (100 normal, 500 debug mode)
   - P50, P95, P99 percentiles
   - Min/max/average tracking

2. **Token Usage** (Lines 156-184)
   - Total, prompt, completion tokens
   - Per-model breakdown
   - Cost estimation support

3. **Error Tracking** (Lines 186-228)
   - Total error count
   - Errors by type
   - Recent error log with timestamps
   - Error rate calculation

4. **Active Stats** (Lines 229-262)
   - Active users/channels (with hourly reset to prevent memory leak)
   - Messages processed
   - Commands executed

5. **Cache Statistics** (Lines 264-313)
   - History cache hit/miss
   - RAG cache hit/miss
   - Hit rate percentages

6. **Service Metrics** (Lines 315-333)
   - TTS generations
   - Vision requests
   - Web searches
   - Summarizations
   - RAG queries

7. **Hourly Trends** (Lines 335-364)
   - Messages per hour (24-hour rolling)
   - Errors per hour
   - Time-series data for trending

**Background Tasks** (Lines 507-661):
- Auto-save metrics every hour
- Daily summary and cleanup
- Hourly active stats reset (prevents memory leak)
- Batch event logging for performance

**Debug Mode Features** (Lines 36, 117-124, 389-392):
- Detailed request logging (last 100 requests)
- Enhanced metrics retention
- Full request context capture

### ContextManager

**File**: `/root/acore_bot/services/core/context.py`

Token-aware prompt construction with intelligent budgeting.

**Purpose** (Lines 1-150):
- Manages LLM context window within token limits
- Prioritizes system prompt, RAG, lorebook over history
- Prevents context overflow
- Multi-persona identity stability

**Token Counting** (Lines 24-65):
- Uses tiktoken for accurate token counting
- Caches encoders for performance
- Model-specific encoding (GPT-4, GPT-3.5, cl100k_base)
- Message overhead accounting (~4 tokens per message)

**Context Building Strategy** (Lines 67-150):
```
Priority Order (High to Low):
1. System Prompt (Always included)
2. User Context / RAG (High Priority)
3. Lorebook Entries (High Priority)
4. Chat History (Fill remaining budget, newest first)
```

**Features**:
- Fetches context limit from LLM service if available
- Falls back to config-based limits
- Reserves 10% tokens for generation
- Multi-persona stability fixes (prevents identity bleeding)
- Timestamp injection for temporal awareness

### RateLimiter

**File**: `/root/acore_bot/services/core/rate_limiter.py`

Controls concurrent requests and API rate limits.

**Features**:
- Semaphore-based concurrency limiting
- Time-based rate limiting (requests per minute)
- Async context manager for easy usage
- Prevents OOM and API throttling

---

## LLM Services

Services for interacting with Large Language Models.

### OllamaService

**File**: `/root/acore_bot/services/llm/ollama.py`

Local Ollama LLM integration with advanced features.

**Architecture** (Lines 112-552):
```python
class OllamaService(LLMInterface):
    def __init__(self, host, model, temperature, max_tokens, ...):
        self.session = aiohttp.ClientSession()
        self.rate_limiter = RateLimiter(max_concurrent=5, rpm=60)
        self.cache = LLMCache(max_size=1000, ttl=3600)
        self.deduplicator = RequestDeduplicator()
```

**Key Features**:

1. **Request Deduplication** (Lines 18-110)
   - Deduplicates identical concurrent requests
   - Uses SHA256 hash of (messages + model + temperature)
   - 5-second cache window for duplicates
   - Prevents redundant API calls

2. **Response Caching** (Lines 161-166, 226-238)
   - LRU cache with TTL
   - Configurable max size and expiration
   - Automatic cache invalidation
   - Cache statistics tracking

3. **Rate Limiting** (Lines 154-159, 275, 357)
   - Max 5 concurrent generations
   - 60 requests per minute limit
   - Prevents OOM on GPU
   - Async semaphore-based

4. **Message Cleaning** (Lines 182-199, 223-224)
   - Removes extra metadata fields (username, user_id)
   - Ensures Ollama API compatibility
   - Prevents field leakage into responses

5. **Streaming Support** (Lines 310-384)
   - Token-by-token streaming
   - Async generator interface
   - JSON Lines parsing
   - 120-second timeout for long responses

6. **Vision Model Support** (Lines 398-469)
   - Multimodal input (text + images)
   - Base64 image encoding
   - Separate vision model selection
   - Configurable via VISION_MODEL

**Sampling Parameters** (Lines 115-151):
- Temperature (0.0-2.0, roleplay: 1.12-1.22)
- Min-P (0.0-1.0, roleplay: 0.075)
- Top-K (roleplay: 50)
- Repeat penalty (roleplay: 1.1)
- Frequency/presence penalties
- Top-P sampling
- Context window (4096 tokens)

**Health Checks** (Lines 470-510):
- `/api/tags` endpoint ping
- Model availability check
- List available models
- Connection verification

### OpenRouterService

**File**: `/root/acore_bot/services/llm/openrouter.py`

Cloud LLM API integration with performance tracking.

**Architecture** (Lines 17-619):
```python
class OpenRouterService(LLMInterface):
    def __init__(self, api_key, model, base_url, temperature, ...):
        self.session = aiohttp.ClientSession(headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/joshhmann/acore_bot",
            "X-Title": "Acore Bot"
        })
        self.cache = LLMCache(...)
```

**Performance Tracking** (Lines 68-74, 189-259):
- Last response time (seconds)
- Tokens per second (TPS)
- Total requests and tokens
- Average response time
- Time To First Token (TTFT) for streaming

**Model-Specific Handling** (Lines 165-170, 317-323):
- Amazon Nova temperature clamping (max 1.0)
- Model context limit fetching from API
- Per-model configuration support

**Streaming Features** (Lines 288-423):
- Server-Sent Events (SSE) parsing
- Chunked response handling
- TTFT measurement
- Token estimation
- Comprehensive error handling

**Context Limit Fetching** (Lines 508-528):
- Fetches context length from OpenRouter API
- Caches model metadata
- Falls back to config limits
- Automatic initialization on startup

**Metrics Reset** (Lines 582-590):
- Prevents unbounded metric growth
- Resets performance counters
- Maintains uptime tracking

### ThinkingService

**File**: `/root/acore_bot/services/llm/thinking.py`

Lightweight LLM for quick internal decisions.

**Purpose** (Lines 9-19):
- Spam detection
- Intent classification
- Yes/No decisions
- Routing choices
- Uses cheaper/faster model to save costs

**Architecture** (Lines 21-68):
- Falls back to main LLM if not configured
- Lazy initialization
- Supports both Ollama and OpenRouter
- Fixed parameters (temp=0.3, max_tokens=50)

**Key Methods** (Lines 69-151):

1. **decide(prompt, default)** - Binary yes/no decision
   - Returns True for YES, False for NO
   - Falls back to default on failure

2. **classify(prompt, options, default)** - Multi-option classification
   - Returns matched option from list
   - Case-insensitive matching
   - Fallback to first option

3. **quick_generate(prompt, max_tokens)** - Short text generation
   - Fast completion for simple tasks
   - Configurable token limit

### LLMFallbackManager

**File**: `/root/acore_bot/services/llm/fallback.py`

Model fallback chain for resilience (like LiteLLM).

**Architecture** (Lines 10-177):
```python
@dataclass
class ModelConfig:
    name: str
    provider: str  # "openrouter", "ollama"
    max_temp: Optional[float]  # Model-specific limits
    cost_tier: str  # "free", "paid", "premium"
    priority: int  # Lower = higher priority
```

**Fallback Strategy** (Lines 41-138):
1. Try primary model first
2. On failure, try next model in chain
3. Auto-adjust temperature if needed (e.g., Nova <= 1.0)
4. Track success/failure stats per model
5. Raise exception if all models fail

**Statistics Tracking** (Lines 29-40, 140-167):
- Total requests
- Fallbacks triggered
- Per-model usage and failures
- Fallback rate percentage
- Primary model success rate

**Usage Example**:
```python
fallback = LLMFallbackManager([
    ModelConfig("google/gemini-2.0-flash-exp:free", "openrouter", priority=0),
    ModelConfig("meta-llama/llama-3.1-8b-instruct:free", "openrouter", priority=1),
    ModelConfig("amazon/nova-micro-v1:free", "openrouter", max_temp=1.0, priority=2)
])

response, model_used = await fallback.chat_with_fallback(
    llm_service, messages, system_prompt, temperature
)
```

### LLMCache

**File**: `/root/acore_bot/services/llm/cache.py`

LRU cache with TTL for LLM responses.

**Features** (Lines 12-209):
- OrderedDict-based LRU eviction
- Configurable max size and TTL
- SHA256 cache key generation
- Automatic expiration on read
- Cache statistics (hits, misses, evictions, TTL expirations)
- Hit rate calculation

**Cache Key Generation** (Lines 43-76):
- Deterministic serialization (sorted JSON)
- Includes: messages, model, temperature, system_prompt
- Rounds temperature to avoid float precision issues
- SHA256 hash for compact keys

**Statistics** (Lines 178-209):
- Hits and misses
- Total requests
- Hit rate percentage
- LRU evictions
- TTL expirations
- Estimated savings per hit (~2-10s and API cost)

---

## Memory Services

Services for managing conversation history, RAG, and long-term memory.

### RAGService

**File**: `/root/acore_bot/services/memory/rag.py`

Retrieval-Augmented Generation with vector embeddings.

**Architecture** (Lines 13-576):
```python
class RAGService:
    def __init__(self, documents_path, vector_store_path, top_k=3):
        self.chroma_client = None  # ChromaDB for vectors
        self.collection = None
        self.embedding_model = None  # sentence-transformers
        self.documents = []  # In-memory document cache
        self.embedding_cache = {}  # Query embedding cache
```

**Features**:

1. **Vector Similarity Search** (Lines 60-105, 266-353)
   - ChromaDB persistent storage
   - sentence-transformers (all-MiniLM-L6-v2)
   - Cosine distance similarity
   - Metadata filtering (category, filename)
   - Category boosting (5x multiplier)

2. **Document Chunking** (Lines 161-199)
   - 500-character chunks with 50-char overlap
   - Sentence boundary detection
   - Preserves context across chunks
   - Metadata tracking per chunk

3. **Keyword Fallback** (Lines 399-520)
   - Stop word filtering
   - Fuzzy matching (plural handling)
   - Exact phrase boosting (2x)
   - Category boosting (5x)
   - **NEW:** Category list filtering (persona-specific)

4. **Document Management** (Lines 106-157, 483-515)
   - Async file loading
   - .txt and .md support
   - Category-based organization
   - Hot-reload capability

5. **Embedding Caching** (Lines 44-46, 282-289)
   - In-memory query cache
   - 500-entry LRU limit
   - Prevents redundant encoding

6. **Persona-Specific Filtering** (Lines 287-292, 506-514) - **NEW 2025-12-10**
   - Characters can specify `rag_categories` to restrict document access
   - Prevents cross-contamination (e.g., Jesus accessing Dagoth's gaming docs)
   - Supports multiple categories with OR logic
   - Debug logging for filtering operations
   - Case-insensitive category matching

**Search Methods**:
- `search(query, top_k, category, categories, boost_category)` - Main search interface
  - **NEW:** `categories` parameter for list-based filtering
  - Debug logging when filtering is applied
- `get_context(query, max_length, category, categories, boost_category)` - Context extraction for prompts
- Relevance threshold (0.5) to prevent low-quality results

**Category Filtering Logic**:
```python
# Vector search uses ChromaDB where clause
where_filter = {"category": {"$in": categories}}

# Keyword search filters in-memory
if categories:
    categories_lower = [c.lower() for c in categories]
    if doc["category"] not in categories_lower:
        continue  # Skip documents outside allowed categories
```

**Statistics** (Lines 552-575):
- Total documents and chunks
- Search method (vector/keyword)
- Category breakdown
- Vector store embeddings count

### ConversationSummarizer

**File**: `/root/acore_bot/services/memory/summarizer.py`

AI-powered conversation summarization with RAG storage.

**Purpose** (Lines 16-347):
- Summarizes long conversations
- Stores summaries in RAG for retrieval
- Builds long-term memory
- Provides relevant past context

**Summarization Strategy** (Lines 42-125):
```
AI-Generated Summary Includes:
1. Main topics discussed
2. Key points and decisions
3. Important facts shared
4. Emotional tone and dynamics
5. Answered questions
6. Notable quotes
```

**Workflow**:
1. **Summarize** (Lines 42-125)
   - Minimum 10 messages required
   - User attribution maintained
   - Thinking process cleaned
   - Metadata captured (timestamp, participants, message count)

2. **Store in RAG** (Lines 127-171)
   - Formatted as searchable document
   - Timestamped filename
   - Category: conversation summaries

3. **Store in Files** (Lines 173-198)
   - JSON backup in summary_dir
   - Includes full metadata
   - Archival and recovery

**Memory Retrieval** (Lines 237-304):
- `retrieve_relevant_memories(query)` - Search past summaries
- `build_memory_context(message)` - Inject relevant memories into prompt
- Relevance threshold (0.1 minimum)
- Max length limiting

**Summary Management** (Lines 306-347):
- List all summaries
- Filter by channel
- Sort by timestamp
- Error handling per file

### MultiTurnConversationManager

**File**: `/root/acore_bot/services/memory/conversation.py`

Manages multi-turn wizard-style conversations.

**Use Cases** (Lines 81-376):
- Server setup wizards
- Persona creation flows
- Reminder series configuration
- Any multi-step data collection

**Architecture** (Lines 21-79):
```python
@dataclass
class ConversationStep:
    prompt: str
    validator: Callable[[str], bool]
    error_message: str
    max_attempts: int = 3
    timeout_seconds: int = 300

@dataclass
class Conversation:
    conversation_id: str
    user_id: int
    channel_id: int
    steps: List[ConversationStep]
    state: ConversationState
    data: Dict[str, Any]  # Collected responses
```

**Conversation States**:
- ACTIVE - Currently running
- WAITING_FOR_INPUT - Awaiting user response
- COMPLETED - Successfully finished
- CANCELLED - User cancelled
- TIMED_OUT - Timeout exceeded

**Built-in Templates** (Lines 94-167):
1. **server_setup** - Configure bot prefix, announcement channel, auto-reply
2. **create_persona** - Character ID, display name, description, system prompt
3. **reminder_series** - Task, frequency, repetition count

**Response Processing** (Lines 224-314):
- Input validation
- Attempt counting (max 3)
- Data storage in conversation.data
- Step advancement
- Cancellation support (keywords: cancel, quit, exit, stop)

**Cleanup** (Lines 342-355):
- Timeout detection
- Auto-cleanup of timed-out conversations
- State tracking

### MemoryManager

**File**: `/root/acore_bot/services/memory/long_term.py`

Automated cleanup and optimization of storage.

**Responsibilities** (Lines 13-295):

1. **Temp File Cleanup** (Lines 45-93)
   - Removes old audio/data files
   - Default: 24-hour retention
   - Frees disk space
   - Statistics tracking

2. **Conversation Archival** (Lines 95-165)
   - Archives old chat history (30+ days)
   - Compresses to archive directory
   - Metadata preservation
   - Prevents unbounded growth

3. **Archive Trimming** (Lines 167-183)
   - Maintains max archived conversations (100)
   - Removes oldest archives
   - FIFO eviction

4. **History Compression** (Lines 230-266)
   - Keeps only recent messages (20)
   - Trims old history files
   - Preserves newest messages

5. **Background Cleanup** (Lines 268-295)
   - Runs every 6 hours
   - Automatic temp and archive cleanup
   - Continuous operation
   - Error resilience

**Storage Statistics** (Lines 184-228):
- Temp files count and size
- History files count and size
- Archived files count and size
- All sizes in MB

---

## Voice Services

Services for speech synthesis and recognition.

### TTSService

**File**: `/root/acore_bot/services/voice/tts.py`

Unified Text-to-Speech interface supporting multiple engines.

**Supported Engines** (Lines 29-108):
1. **Kokoro API** (HTTP API)
   - Fast, low-latency
   - Remote processing
   - Recommended for production

2. **Kokoro** (In-process)
   - Local ONNX models
   - No network dependency
   - Higher CPU usage

3. **Supertonic** (In-process)
   - High-quality synthesis
   - Denoising steps (configurable)
   - More compute-intensive

**Text Cleaning** (Lines 132-139):
- Removes emojis
- Strips asterisks and markdown
- Cleans special characters
- Uses `utils.helpers.clean_text_for_tts()`

**Generation Flow** (Lines 109-191):
1. Clean input text
2. Select engine (Supertonic/Kokoro API/Kokoro)
3. Apply voice and speed settings
4. Run in executor if sync (Supertonic)
5. Return audio file path

**Voice Management** (Lines 193-200):
- Engine-specific voice lists
- Voice parameter validation
- Default voice configuration

### UnifiedRVCService

**File**: `/root/acore_bot/services/voice/rvc.py`

Voice conversion using RVC (Retrieval-based Voice Conversion).

**Modes**:
- **Local** - In-process RVC model
- **WebUI** - HTTP API to RVC WebUI

**Features**:
- Model loading and management
- Pitch shifting
- Voice cloning
- Speaker conversion

### EnhancedVoiceListener

**File**: `/root/acore_bot/services/voice/listener.py`

Voice activity detection and wake word triggering.

**Features**:
- Silence threshold detection
- Energy-based VAD
- Trigger word recognition
- Integration with STT service

### ParakeetAPIService

**File**: `/root/acore_bot/services/clients/stt_client.py`

Speech-to-Text via Parakeet API.

**Features**:
- Async audio transcription
- Language configuration
- Health check endpoint
- Error handling

---

## Persona Services

AI personality and behavior management.

### PersonaSystem

**File**: `/root/acore_bot/services/persona/system.py`

Framework + Character loader and compiler.

**Architecture** (Lines 14-273):
```python
@dataclass
class Framework:
    framework_id: str  # "neuro", "assistant"
    name: str
    purpose: str
    behavioral_patterns: Dict
    tool_requirements: Dict
    decision_making: Dict
    context_requirements: Dict
    interaction_style: Dict
    anti_hallucination: Dict
    prompt_template: str

@dataclass
class Character:
    character_id: str  # "dagoth_ur", "arbiter"
    display_name: str
    identity: Dict
    knowledge_domain: Dict
    opinions: Dict
    voice_and_tone: Dict
    quirks: Dict
    avatar_url: Optional[str]
    # V2 Card fields
    description: str
    scenario: str
    first_message: str
    mes_example: str
    alternate_greetings: List[str]
    system_prompt_override: str

@dataclass
class CompiledPersona:
    persona_id: str
    character: Character
    framework: Framework
    system_prompt: str  # Compiled from framework + character
    tools_required: List[str]
    config: Dict
```

**Loading Process**:
1. **Load Framework** (Lines 92-138)
   - Read from `prompts/frameworks/{id}.json`
   - Cache in memory
   - Contains behavioral rules

2. **Load Character** (Lines 140-186)
   - JSON or PNG (V2 card)
   - PNG uses base64-encoded metadata
   - V2 spec with chunked data
   - Legacy format deprecated

3. **Compile Persona** (Lines 240-273)
   - Merge framework + character
   - Generate system prompt from template
   - Identify required tools
   - Cache compiled result

**V2 Character Card Support** (Lines 190-239):
- PNG with embedded JSON (chara chunk)
- Base64 decoding
- Spec version detection
- Backwards compatibility

**File Locations**:
- Frameworks: `prompts/frameworks/`
- Characters: `prompts/characters/`
- Compiled: `prompts/compiled/`

### BehaviorEngine

**File**: `/root/acore_bot/services/persona/behavior.py`

Central brain for bot autonomy and responsiveness.

**Replaces** (Lines 43-53):
- NaturalnessEnhancer
- AmbientMode
- ProactiveEngagement
- MoodSystem
- EnvironmentalAwareness
- CuriositySystem

**Architecture** (Lines 24-110):
```python
@dataclass
class BehaviorState:
    last_message_time: datetime
    last_bot_message_time: datetime
    message_count: int
    recent_topics: deque
    recent_users: Set[str]
    last_ambient_trigger: datetime
    last_proactive_trigger: datetime
    short_term_memories: List[Dict]

class BehaviorEngine:
    def __init__(self, bot, ollama, context_manager, lorebook, thinking):
        self.states: Dict[int, BehaviorState]  # Per-channel state
        self.current_persona = None
```

**Decision Making** (Lines 112-150):
1. **handle_message(message)** - Process new messages
   - Decide on emoji reactions (15% chance)
   - Decide on proactive engagement
   - Return action directives

2. **Reaction Logic** (Lines 132)
   - Emoji reaction probability
   - Content-based selection
   - Natural response pattern

3. **Proactive Engagement** (Lines 136-147)
   - Only if not mentioned
   - Not in reply chain
   - Considers conversation context
   - Cooldown enforcement

**Ambient Mode** (Lines 151-200):
- Triggers during lulls (1-8 hour silence)
- Minimum 6-hour interval between ambient messages
- 1/6 chance to speak (~16.7%)
- AI-FIRST spam check via thinking LLM
- Evaluates if message would be annoying

**Background Loop** (Lines 151-160):
- 60-second tick interval
- Checks all active channels
- Detects silence duration
- Schedules ambient messages

**Configuration**:
- `reaction_chance`: 0.15 (15%)
- `ambient_interval_min`: 600s (10 min)
- `ambient_chance`: 0.3 (30%)
- `proactive_cooldown`: Seconds between engagements

### LorebookService

**File**: `/root/acore_bot/services/persona/lorebook.py`

World information injection system.

**Features**:
- Keyword-triggered lore entries
- Context injection
- Character knowledge base
- Dynamic world building

### PersonaRelationships

**File**: `/root/acore_bot/services/persona/relationships.py`

Tracks relationships and affinity between users and personas.

**Features**:
- Affinity scoring
- Relationship history
- Pattern learning
- User-specific memories

### EvolutionSystem (NEW)

**File**: `/root/acore_bot/services/persona/evolution.py`

**Purpose**: Character progression system that unlocks new behaviors and capabilities through interaction milestones.

**Initialization**: Lazy-loaded by `BehaviorEngine` when needed.

**Architecture** (Lines 25-120):
```python
@dataclass
class EvolutionMilestone:
    milestone_id: str
    name: str
    description: str
    requirements: Dict[str, Any]  # Messages, relationships, etc.
    unlocks: List[str]  # New behaviors, responses, etc.
    xp_reward: int
    character_specific: Optional[str] = None

@dataclass
class CharacterEvolution:
    character_id: str
    current_level: int
    total_xp: int
    unlocked_milestones: List[str]
    active_traits: List[str]
    evolution_history: List[Dict]
```

**Core Evolution Mechanics**:

#### 1. Experience System (Lines 150-250)
- **Message XP**: Earn experience through meaningful conversations
- **Quality over Quantity**: Longer, engaging conversations worth more XP
- **Relationship Bonus**: Higher relationship levels multiply XP gains
- **Topic Diversity**: Exploring different topics grants bonus XP
- **Daily Limits**: Prevents grinding, encourages natural interaction

#### 2. Milestone System (Lines 300-450)
```python
# Example Milestones
milestones = [
    {
        "id": "first_friendship",
        "name": "First Friend",
        "description": "Build a meaningful relationship with a user",
        "requirements": {"relationship_level": 60, "interactions": 50},
        "unlocks": ["empathy_responses", "memory_recall"],
        "xp_reward": 100
    },
    {
        "id": "knowledge_seeker",
        "name": "Knowledge Seeker",
        "description": "Engage in 20 different topic discussions",
        "requirements": {"unique_topics": 20, "conversation_depth": 3},
        "unlocks": ["topic_expertise", "cross_reference"],
        "xp_reward": 150
    }
]
```

#### 3. Trait Unlocks (Lines 500-650)
- **Behavioral Traits**: New response patterns and mannerisms
- **Knowledge Traits**: Access to specialized information
- **Social Traits**: Enhanced relationship-building capabilities
- **Emotional Traits**: Deeper emotional range and understanding

**Trait Categories**:
- **Communication**: Sarcasm, empathy, humor styles
- **Knowledge**: Expertise areas, learning capabilities
- **Social**: Banter skills, comfort levels, leadership
- **Emotional**: Emotional range, empathy depth, mood stability

#### 4. Character-Specific Evolution (Lines 700-850)
Each character has unique evolution paths:

**Dagoth Ur Evolution Path**:
- **Level 1**: Standard divine responses
- **Level 5**: Unlocks philosophical depth
- **Level 10**: Gains mentorship capabilities
- **Level 15**: Develops wisdom and guidance traits

**Scav Evolution Path**:
- **Level 1**: Basic scavenger slang
- **Level 5**: Unlocks advanced Tarkov knowledge
- **Level 10**: Gains storytelling abilities
- **Level 15**: Develops protective instincts

#### 5. Evolution Persistence (Lines 900-1000)
- **Auto-Save**: Evolution progress saved every 5 minutes
- **Backup System**: Daily backups to prevent data loss
- **Migration Support**: Export/import evolution data
- **Reset Capability**: Optional character reset (with confirmation)

**Analytics Integration**:
- **Evolution Tracking**: Monitor character progression rates
- **Milestone Analytics**: Most/least completed milestones
- **Trait Usage**: Track which unlocked traits are used most
- **Engagement Metrics**: Evolution impact on user engagement

**Configuration**:
```python
# Evolution System Settings
EVOLUTION_ENABLED=true
XP_PER_MESSAGE_BASE=1
XP_MULTIPLIER_RELATIONSHIP=1.5
MAX_DAILY_XP=100
MILESTONE_NOTIFICATIONS=true
EVOLUTION_SAVE_INTERVAL=300  # 5 minutes
```

**Web Dashboard Integration**:
- Character evolution trees visualization
- Progress tracking with interactive charts
- Milestone completion analytics
- Trait unlock history

---

## Analytics Services (NEW)

Real-time monitoring and dashboard services for production insights.

### AnalyticsDashboard

**File**: `/root/acore_bot/services/analytics/dashboard.py`

**Purpose**: FastAPI-based real-time dashboard for monitoring bot performance, persona interactions, and system health.

**Note**: Initialized in `main.py` to run as a separate server process.

**Architecture** (Lines 25-150):
```python
class AnalyticsDashboard:
    def __init__(self, host, port, api_key=None):
        self.app = FastAPI(title="Acore Bot Analytics")
        self.host = host
        self.port = port
        self.api_key = api_key
        self.metrics_service = None  # Injected by ServiceFactory
        self.persona_system = None   # Injected by ServiceFactory
```

**Core Features**:

#### 1. Real-Time Metrics WebSocket (Lines 200-280)
- **Live Updates**: WebSocket endpoint `/ws/metrics` streams real-time data
- **Persona Analytics**: Individual character statistics, interaction counts
- **Performance Metrics**: Response times, token usage, error rates
- **System Health**: Memory usage, CPU, service status
- **User Analytics**: Active users, message rates, engagement patterns

#### 2. REST API Endpoints (Lines 100-199)
```python
# Main dashboard UI
@app.get("/")
async def dashboard():
    # Serves interactive React-based dashboard

# JSON metrics endpoints
@app.get("/api/metrics")
async def get_metrics():
    # Returns current metrics as JSON

# Health check endpoint
@app.get("/api/health")
async def health_check():
    # Service health status

# Persona-specific analytics
@app.get("/api/personas/{persona_id}")
async def get_persona_analytics(persona_id: str):
    # Individual character statistics

# Historical data
@app.get("/api/history/{metric}")
async def get_historical_data(metric: str, days: int = 7):
    # Time-series data for charts
```

#### 3. Dashboard Features
- **Interactive Charts**: D3.js-powered visualizations
- **Real-Time Updates**: WebSocket-powered live data streams
- **Custom Time Ranges**: Filter data by date/time
- **Export Capabilities**: Download metrics as CSV/JSON
- **Alert System**: Configurable thresholds with notifications
- **Multi-Server Support**: Track metrics across multiple Discord servers

#### 4. Persona Analytics (Lines 300-400)
```python
# Per-Persona Metrics
persona_stats = {
    "dagoth_ur": {
        "message_count": 1234,
        "avg_response_time": 2.3,
        "user_satisfaction": 4.7,
        "top_topics": ["morrowind", "philosophy", "divinity"],
        "relationship_levels": {"user123": 85, "user456": 62},
        "emotional_state": "confident",
        "active_channels": ["general", "gaming"],
        "peak_hours": [20, 21, 22]  # 8-10 PM
    }
}
```

#### 5. Security & Authentication (Lines 50-99)
- **API Key Protection**: Optional API key for sensitive endpoints
- **CORS Configuration**: Cross-origin requests for dashboard frontend
- **Rate Limiting**: Prevent API abuse (100 requests/minute)
- **Request Logging**: Audit trail for analytics access

**WebSocket Message Format**:
```json
{
    "type": "metrics_update",
    "timestamp": "2025-12-12T10:30:00Z",
    "data": {
        "active_users": 45,
        "messages_per_minute": 12.5,
        "avg_response_time_ms": 1850,
        "error_rate": 0.02,
        "personas": {
            "dagoth_ur": {"messages": 23, "sentiment": 0.3},
            "scav": {"messages": 17, "sentiment": -0.1}
        }
    }
}
```

**Configuration**:
```python
# Analytics Dashboard Settings
ANALYTICS_ENABLED=true
ANALYTICS_HOST=localhost
ANALYTICS_PORT=8000
ANALYTICS_API_KEY=your_secure_key_here
ANALYTICS_CORS_ORIGINS=["http://localhost:3000"]
METRICS_RETENTION_DAYS=30
```

**Deployment**:
- **Standalone Mode**: Runs alongside bot in same process
- **Docker Support**: Containerized deployment available
- **Reverse Proxy**: Nginx configuration for production
- **SSL/TLS**: HTTPS support for secure dashboard access

---

## Discord Services

Discord-specific feature services.

### UserProfileService

**File**: `/root/acore_bot/services/discord/profiles.py`

User profile management with AI-powered updates.

**Features**:
- Profile creation and storage
- AI-generated profile updates
- Fact extraction from conversations
- JSON persistence
- Profile retrieval for context

### WebSearchService

**File**: `/root/acore_bot/services/discord/web_search.py`

Web search integration.

**Supported Engines**:
- DuckDuckGo
- Google (with API key)

**Features**:
- Configurable max results
- Result formatting
- Error handling
- Rate limiting

### RemindersService

**File**: `/root/acore_bot/services/discord/reminders.py`

Scheduled reminder system.

**Features**:
- Create/delete reminders
- Natural language time parsing
- Persistent storage
- Background check loop
- Discord notifications

### NotesService

**File**: `/root/acore_bot/services/discord/notes.py`

Simple note-taking system.

**Features**:
- Per-user note storage
- Add/list/delete operations
- JSON persistence
- Private notes

---

## Service Factory

**File**: `/root/acore_bot/services/core/factory.py`

The ServiceFactory is the central initialization hub for all services.

### Initialization Methods

**`_init_llm()`** (Lines 72-126):
- Selects LLM provider (Ollama or OpenRouter)
- Configures sampling parameters
- Initializes fallback manager
- Creates thinking service

**`_init_audio()`** (Lines 127-174):
- Initializes TTS engine
- Sets up RVC if enabled
- Configures STT (Parakeet)
- Creates voice listener

**`_init_data()`** (Lines 175-221):
- Chat history manager
- User profiles
- RAG service
- Memory manager
- Conversation summarizer

**`_init_features()`** (Lines 222-247):
- Web search
- Reminders
- Notes
- Conversation manager

**`_init_ai_systems()`** (Lines 248-273):
- Persona system
- Compiled persona
- Tool system
- Persona relationships

### Service Access

Services are stored in `self.services` dictionary:
```python
services = factory.create_services()
ollama = services['ollama']
tts = services['tts']
rag = services['rag']
```

### Conditional Initialization

Services are only initialized if enabled in config:
```python
if Config.RAG_ENABLED:
    services['rag'] = RAGService(...)
else:
    services['rag'] = None
```

---

## Integration Patterns

### Dependency Injection

Services receive dependencies through constructor injection:
```python
# ServiceFactory injects dependencies
summarizer = ConversationSummarizer(
    ollama=services['ollama'],
    rag=services['rag'],
    summary_dir=Config.SUMMARY_DIR
)
```

### Service Interfaces

All major services implement interfaces for swappability:
```python
# Can swap LLM providers without changing code
llm: LLMInterface = OllamaService(...)
# or
llm: LLMInterface = OpenRouterService(...)

# Both support same methods
response = await llm.chat(messages, system_prompt)
```

### Factory Pattern

ServiceFactory uses factory pattern for centralized initialization:
```python
factory = ServiceFactory(bot)
services = factory.create_services()

# All services initialized with correct dependencies
# All config applied
# All conditional logic handled
```

### Context Manager Pattern

Many services use context managers for resource management:
```python
# MetricsService timer
with metrics.timer():
    response = await llm.chat(messages)

# RateLimiter acquire
async with rate_limiter.acquire():
    response = await api_call()
```

### Async/Await Pattern

All I/O-bound operations are async:
```python
# LLM requests
response = await ollama.chat(messages)

# File operations
async with aiofiles.open(path, 'r') as f:
    content = await f.read()

# API calls
async with session.post(url, json=payload) as resp:
    data = await resp.json()
```

### Observer Pattern

Services emit events for metrics tracking:
```python
# Record in metrics
metrics.record_response_time(duration_ms)
metrics.record_token_usage(prompt_tokens, completion_tokens)
metrics.record_error("APIError", str(e))
```

### Strategy Pattern

Services support multiple strategies via configuration:
```python
# TTS engine selection
if engine == "kokoro_api":
    use_kokoro_api()
elif engine == "kokoro":
    use_kokoro_local()
elif engine == "supertonic":
    use_supertonic()

# LLM provider selection
if Config.LLM_PROVIDER == "openrouter":
    llm = OpenRouterService(...)
else:
    llm = OllamaService(...)
```

### Cache-Aside Pattern

LLM cache uses cache-aside:
```python
# Check cache
cached = cache.get(messages, model, temperature)
if cached:
    return cached

# Generate response
response = await api_call()

# Store in cache
cache.set(messages, model, temperature, response)
return response
```

### Circuit Breaker Pattern

LLM fallback implements circuit breaker:
```python
for model in fallback_chain:
    try:
        response = await llm.chat(messages)
        return response, model
    except Exception as e:
        # Try next model
        continue

# All models failed
raise Exception("All models failed")
```

---

## Summary

The service layer provides:

1. **LLM Integration** - Ollama, OpenRouter, fallback, caching, thinking
2. **Memory Management** - RAG, summaries, history, cleanup
3. **Voice Processing** - TTS (multiple engines), STT, RVC
4. **Persona System** - Framework + character, behavior engine, relationships
5. **Discord Features** - Profiles, web search, reminders, notes
6. **Core Infrastructure** - Metrics, context, rate limiting, factory

All services follow:
- Interface-based design
- Dependency injection
- Async/await patterns
- Comprehensive error handling
- Configurable behavior
- Metrics tracking
