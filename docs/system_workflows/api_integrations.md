# API Integrations System Workflow

This document describes the complete API integrations system in acore_bot, including external service connections, API clients, data synchronization, and third-party service workflows.

## Overview

The API integrations system enables **external service connectivity** through **API clients**, **data synchronization**, **service abstraction layers**, and **fallback mechanisms** for robust integration with third-party services.

## Architecture

### Component Structure
```
services/
├── interfaces/            # API interface abstractions
│   ├── llm_interface.py   # LLM service interface
│   ├── tts_interface.py    # TTS service interface
│   ├── stt_interface.py    # STT service interface
│   └── rvc_interface.py   # RVC service interface
├── clients/                # External API clients
│   ├── tts_client.py       # TTS API clients
│   ├── stt_client.py       # STT API clients
│   └── rvc_client.py       # RVC API clients
├── llm/                   # LLM integrations
│   ├── ollama.py           # Ollama LLM client
│   ├── openrouter.py        # OpenRouter LLM client
│   ├── fallback.py          # LLM fallback system
│   ├── cache.py            # Response caching
│   └── tools.py            # LLM tool integration
└── discord/                # Discord service integrations
    ├── web_search.py       # Web search API
    ├── music.py            # Music service APIs
    ├── profiles.py         # Profile data APIs
    └── reminders.py        # External reminder APIs

config/                     # API configuration
└── api_keys.example        # API key template
```

### Service Dependencies
```
API Integration Dependencies:
├── HTTP Clients            # Async HTTP requests
├── Authentication         # API key management
├── Rate Limiting         # Request throttling
├── Error Handling        # API error recovery
├── Caching              # Response caching
├── Retry Logic          # Failed request retry
└── Monitoring           # API performance tracking
```

## LLM Integration System

### 1. LLM Interface Abstraction
**File**: `services/interfaces/llm_interface.py:45-123`

#### 1.1 Abstract LLM Interface
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator
import asyncio

class LLMInterface(ABC):
    """Abstract interface for LLM services."""
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate a chat response."""
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming chat response."""
        pass
    
    @abstractmethod
    async def embed(
        self,
        text: str,
        model: Optional[str] = None
    ) -> List[float]:
        """Generate text embeddings."""
        pass
    
    @abstractmethod
    async def models(self) -> List[Dict[str, str]]:
        """List available models."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, any]:
        """Check API health status."""
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Cleanup resources."""
        pass

class LLMResponse:
    """Standard LLM response wrapper."""
    
    def __init__(
        self,
        content: str,
        model: str,
        usage: Dict[str, int],
        finish_reason: str,
        response_time: float,
        metadata: Optional[Dict] = None
    ):
        self.content = content
        self.model = model
        self.usage = usage
        self.finish_reason = finish_reason
        self.response_time = response_time
        self.metadata = metadata or {}
```

### 2. Ollama LLM Client
**File**: `services/llm/ollama.py:45-234`

#### 2.1 Ollama Service Implementation
```python
import aiohttp
import json
from typing import List, Dict, Optional, AsyncGenerator

class OllamaService(LLMInterface):
    """Ollama LLM service implementation."""
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: int = 120
    ):
        self.host = host.rstrip('/')
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None
        
        # Generation parameters
        self.default_params = {
            'temperature': float(Config.OLLAMA_TEMPERATURE),
            'top_p': float(Config.OLLAMA_TOP_P),
            'min_p': float(Config.OLLAMA_MIN_P),
            'repeat_penalty': float(Config.OLLAMA_REPEAT_PENALTY),
            'top_k': int(Config.OLLAMA_TOP_K)
        }

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
        return self.session

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate chat response using Ollama."""
        
        try:
            session = await self._get_session()
            
            # Prepare request
            payload = {
                'model': self.model,
                'messages': messages,
                'stream': False,
                'options': {
                    **self.default_params,
                    'temperature': temperature,
                    'num_predict': max_tokens or Config.OLLAMA_MAX_TOKENS
                }
            }
            
            # Override with additional parameters
            payload['options'].update(kwargs)
            
            # Make request
            start_time = time.time()
            
            async with session.post(
                f"{self.host}/api/chat",
                json=payload
            ) as response:
                
                response.raise_for_status()
                data = await response.json()
                
                response_time = time.time() - start_time
                
                if 'message' in data:
                    return LLMResponse(
                        content=data['message']['content'],
                        model=self.model,
                        usage=data.get('usage', {}),
                        finish_reason=data.get('done_reason', 'stop'),
                        response_time=response_time,
                        metadata={
                            'model_info': data.get('model', {}),
                            'created_at': data.get('created_at'),
                            'done': data.get('done', False)
                        }
                    )
                else:
                    raise ValueError("Invalid response format from Ollama")
        
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming chat response."""
        
        try:
            session = await self._get_session()
            
            # Prepare request
            payload = {
                'model': self.model,
                'messages': messages,
                'stream': True,
                'options': {
                    **self.default_params,
                    'temperature': temperature,
                    'num_predict': max_tokens or Config.OLLAMA_MAX_TOKENS
                }
            }
            
            payload['options'].update(kwargs)
            
            # Make streaming request
            async with session.post(
                f"{self.host}/api/chat",
                json=payload
            ) as response:
                
                response.raise_for_status()
                
                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            
                            if 'message' in data and 'content' in data['message']:
                                yield data['message']['content']
                            
                            if data.get('done', False):
                                break
                                
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            raise

    async def models(self) -> List[Dict[str, str]]:
        """List available Ollama models."""
        
        try:
            session = await self._get_session()
            
            async with session.get(f"{self.host}/api/tags") as response:
                response.raise_for_status()
                data = await response.json()
                
                models = []
                for model in data.get('models', []):
                    model_info = {
                        'name': model.get('name', ''),
                        'size': model.get('details', {}).get('parameter_size', ''),
                        'modified_at': model.get('modified_at', ''),
                        'digest': model.get('digest', '')
                    }
                    models.append(model_info)
                
                return models
                
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
            return []

    async def health_check(self) -> Dict[str, any]:
        """Check Ollama service health."""
        
        try:
            session = await self._get_session()
            
            # Check basic connectivity
            start_time = time.time()
            async with session.get(f"{self.host}/api/tags", timeout=5) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    return {
                        'status': 'healthy',
                        'response_time': response_time,
                        'model_count': len(await self.models()),
                        'current_model': self.model,
                        'host': self.host
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'error': f'HTTP {response.status}',
                        'host': self.host
                    }
                    
        except asyncio.TimeoutError:
            return {
                'status': 'unhealthy',
                'error': 'Connection timeout',
                'host': self.host
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'host': self.host
            }

    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
```

### 3. LLM Fallback System
**File**: `services/llm/fallback.py:45-189`

#### 3.1 Multi-Provider Fallback Manager
```python
class LLMMultiProvider:
    """Manages multiple LLM providers with fallback logic."""
    
    def __init__(self):
        self.providers = {}
        self.primary_provider = None
        self.fallback_chain = []
        self.health_cache = {}
        self.last_health_check = {}
        
        # Configure providers
        self._setup_providers()

    def _setup_providers(self):
        """Setup configured LLM providers."""
        
        # Primary provider (based on config)
        if Config.LLM_PROVIDER == 'ollama':
            self.primary_provider = OllamaService(
                host=Config.OLLAMA_HOST,
                model=Config.OLLAMA_MODEL
            )
        elif Config.LLM_PROVIDER == 'openrouter':
            self.primary_provider = OpenRouterService(
                api_key=Config.OPENROUTER_API_KEY,
                model=Config.OPENROUTER_MODEL
            )
        
        self.providers[Config.LLM_PROVIDER] = self.primary_provider
        
        # Setup fallback chain if enabled
        if Config.LLM_FALLBACK_ENABLED:
            self._setup_fallback_chain()

    def _setup_fallback_chain(self):
        """Setup fallback provider chain."""
        
        fallback_models = Config.LLM_FALLBACK_MODELS.split(',')
        
        for model_spec in fallback_models:
            if not model_spec.strip():
                continue
                
            # Parse model specification
            parts = model_spec.split(':')
            if len(parts) != 2:
                logger.warning(f"Invalid fallback model format: {model_spec}")
                continue
                
            model_name, provider_type = parts[0].strip(), parts[1].strip()
            
            # Create provider based on type
            if provider_type == 'free':
                # Use free tier provider
                provider = self._create_free_provider(model_name)
            elif provider_type == 'paid':
                # Use paid tier provider
                provider = self._create_paid_provider(model_name)
            else:
                continue
            
            if provider:
                self.fallback_chain.append(provider)
                self.providers[model_name] = provider

    async def chat_with_fallback(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Chat with automatic fallback to other providers."""
        
        # Try primary provider first
        providers_to_try = [self.primary_provider] + self.fallback_chain
        
        for i, provider in enumerate(providers_to_try):
            try:
                # Check provider health if not recently checked
                provider_name = self._get_provider_name(provider)
                
                if not await self._is_provider_healthy(provider):
                    if i == 0:
                        logger.warning(f"Primary provider {provider_name} unhealthy, trying fallback")
                    continue
                
                # Attempt generation
                response = await provider.chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                # Track successful provider
                response.metadata['provider_used'] = provider_name
                response.metadata['fallback_used'] = i > 0
                
                if i > 0:
                    logger.info(f"Fallback to {provider_name} successful")
                
                return response
                
            except Exception as e:
                logger.error(f"Provider {self._get_provider_name(provider)} failed: {e}")
                
                if i == 0:
                    logger.info("Primary provider failed, trying fallback")
                continue
        
        # All providers failed
        raise Exception("All LLM providers failed to generate response")

    async def chat_stream_with_fallback(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[LLMResponse, None]:
        """Streaming chat with fallback."""
        
        # For streaming, we try providers sequentially
        providers_to_try = [self.primary_provider] + self.fallback_chain
        
        for i, provider in enumerate(providers_to_try):
            try:
                if not await self._is_provider_healthy(provider):
                    continue
                
                # Stream from this provider
                accumulated_content = ""
                start_time = time.time()
                
                async for chunk in provider.chat_stream(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                ):
                    accumulated_content += chunk
                    yield LLMResponse(
                        content=chunk,
                        model=getattr(provider, 'model', 'unknown'),
                        usage={},
                        finish_reason='streaming',
                        response_time=time.time() - start_time,
                        metadata={
                            'provider_used': self._get_provider_name(provider),
                            'fallback_used': i > 0,
                            'stream_chunk': True
                        }
                    )
                
                # Final response
                yield LLMResponse(
                    content='',
                    model=getattr(provider, 'model', 'unknown'),
                    usage={},
                    finish_reason='stop',
                    response_time=time.time() - start_time,
                    metadata={
                        'provider_used': self._get_provider_name(provider),
                        'fallback_used': i > 0,
                        'stream_complete': True,
                        'total_content': accumulated_content
                    }
                )
                
                return
                
            except Exception as e:
                logger.error(f"Provider {self._get_provider_name(provider)} streaming failed: {e}")
                
                if i == 0:
                    logger.info("Primary provider streaming failed, trying fallback")
                continue
        
        raise Exception("All LLM providers failed to stream response")

    async def _is_provider_healthy(self, provider: LLMInterface) -> bool:
        """Check if provider is healthy with caching."""
        
        provider_name = self._get_provider_name(provider)
        now = time.time()
        
        # Check cache
        if (provider_name in self.health_cache and 
            provider_name in self.last_health_check and
            now - self.last_health_check[provider_name] < 60):  # Cache for 1 minute
            return self.health_cache[provider_name]
        
        try:
            health = await provider.health_check()
            is_healthy = health.get('status') == 'healthy'
            
            # Update cache
            self.health_cache[provider_name] = is_healthy
            self.last_health_check[provider_name] = now
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed for {provider_name}: {e}")
            self.health_cache[provider_name] = False
            self.last_health_check[provider_name] = now
            return False
```

## TTS Integration System

### 1. TTS Interface and Clients
**File**: `services/clients/tts_client.py:45-156`

#### 1.1 Kokoro TTS API Client
```python
class KokoroAPIClient:
    """Kokoro TTS API client for remote TTS service."""
    
    def __init__(
        self,
        api_url: str,
        default_voice: str = "am_adam",
        speed: float = 1.0,
        api_key: Optional[str] = None
    ):
        self.api_url = api_url.rstrip('/')
        self.default_voice = default_voice
        self.speed = speed
        self.api_key = api_key
        self.session = None
        
        # Available voices (will be fetched)
        self.available_voices = []
        self.last_voice_fetch = 0

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {'Content-Type': 'application/json'}
            
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers=headers
            )
        
        return self.session

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        output_format: str = "wav"
    ) -> bytes:
        """Synthesize speech from text."""
        
        try:
            session = await self._get_session()
            
            # Prepare request
            payload = {
                'text': text,
                'voice': voice or self.default_voice,
                'speed': speed or self.speed,
                'format': output_format
            }
            
            # Make request
            async with session.post(
                f"{self.api_url}/synthesize",
                json=payload
            ) as response:
                
                response.raise_for_status()
                
                # Check if response is audio data
                content_type = response.headers.get('content-type', '')
                if 'audio' in content_type:
                    return await response.read()
                else:
                    # Maybe JSON error
                    text_response = await response.text()
                    raise ValueError(f"Expected audio data, got: {text_response}")
                    
        except Exception as e:
            logger.error(f"Kokoro TTS synthesis error: {e}")
            raise

    async def get_voices(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """Get available voices from API."""
        
        now = time.time()
        if (not force_refresh and 
            self.available_voices and 
            now - self.last_voice_fetch < 3600):  # Cache for 1 hour
            return self.available_voices
        
        try:
            session = await self._get_session()
            
            async with session.get(f"{self.api_url}/voices") as response:
                response.raise_for_status()
                data = await response.json()
                
                self.available_voices = data.get('voices', [])
                self.last_voice_fetch = now
                
                return self.available_voices
                
        except Exception as e:
            logger.error(f"Error fetching Kokoro voices: {e}")
            return self.available_voices  # Return cached voices

    async def get_voice_info(self) -> Dict[str, any]:
        """Get current voice configuration."""
        
        return {
            'engine': 'kokoro_api',
            'voice': self.default_voice,
            'speed': self.speed,
            'api_url': self.api_url,
            'available_voices': await self.get_voices()
        }

    async def health_check(self) -> Dict[str, any]:
        """Check TTS service health."""
        
        try:
            session = await self._get_session()
            
            start_time = time.time()
            async with session.get(f"{self.api_url}/health", timeout=5) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    health_data = await response.json()
                    
                    return {
                        'status': 'healthy',
                        'response_time': response_time,
                        'api_url': self.api_url,
                        'voice_count': len(await self.get_voices()),
                        'service_info': health_data
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'error': f'HTTP {response.status}',
                        'api_url': self.api_url
                    }
                    
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'api_url': self.api_url
            }

    async def close(self):
        """Close aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
```

## Web Search Integration

### 1. Web Search Service
**File**: `services/discord/web_search.py:45-189`

#### 1.1 Multi-Engine Web Search
```python
class WebSearchService:
    """Multi-engine web search service."""
    
    def __init__(self):
        self.search_engines = {
            'duckduckgo': DuckDuckGoSearch(),
            'google': GoogleSearch(),
            'bing': BingSearch()
        }
        
        self.current_engine = Config.WEB_SEARCH_ENGINE
        self.max_results = Config.WEB_SEARCH_MAX_RESULTS
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    async def search_web(self, query: str) -> Dict[str, any]:
        """Search the web using configured engine."""
        
        try:
            # Check cache first
            cache_key = f"web:{query}:{self.current_engine}"
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result:
                return cached_result
            
            # Get search engine
            search_engine = self.search_engines.get(self.current_engine)
            
            if not search_engine:
                raise ValueError(f"Unknown search engine: {self.current_engine}")
            
            # Perform search
            results = await search_engine.search(
                query=query,
                max_results=self.max_results
            )
            
            # Format results
            formatted_results = {
                'query': query,
                'source': self.current_engine,
                'results': results,
                'timestamp': time.time()
            }
            
            # Cache results
            self._cache_result(cache_key, formatted_results)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {
                'query': query,
                'source': self.current_engine,
                'results': [],
                'error': str(e)
            }

    async def search_wikipedia(self, query: str) -> Dict[str, any]:
        """Search Wikipedia specifically."""
        
        try:
            # Check cache
            cache_key = f"wiki:{query}"
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result:
                return cached_result
            
            # Use Wikipedia API
            search_url = "https://en.wikipedia.org/api/rest_v1/page/summary"
            params = {
                'redirect': 'true',
                'format': 'json'
            }
            
            # First try to get page directly
            url = f"{search_url}/{quote(query)}"
            
            session = aiohttp.ClientSession()
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        page_data = await response.json()
                        
                        result = {
                            'title': page_data.get('title', ''),
                            'summary': page_data.get('extract', ''),
                            'url': page_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                            'thumbnail': page_data.get('thumbnail', {}).get('source', ''),
                            'timestamp': time.time()
                        }
                        
                        self._cache_result(cache_key, result)
                        return result
                    
                    # If not found, try search
                    search_params = {
                        'action': 'query',
                        'format': 'json',
                        'list': 'search',
                        'srsearch': query,
                        'srlimit': 5
                    }
                    
                    search_url = "https://en.wikipedia.org/w/api.php"
                    
                    async with session.get(search_url, params=search_params) as search_response:
                        if search_response.status == 200:
                            search_data = await search_response.json()
                            search_results = search_data.get('query', {}).get('search', [])
                            
                            if search_results:
                                # Use first search result
                                first_result = search_results[0]
                                page_title = first_result['title']
                                
                                # Get page summary
                                page_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(page_title)}"
                                
                                async with session.get(page_url) as page_response:
                                    if page_response.status == 200:
                                        page_data = await page_response.json()
                                        
                                        result = {
                                            'title': page_data.get('title', ''),
                                            'summary': page_data.get('extract', ''),
                                            'url': page_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                                            'thumbnail': page_data.get('thumbnail', {}).get('source', ''),
                                            'timestamp': time.time()
                                        }
                                        
                                        self._cache_result(cache_key, result)
                                        return result
                        
            finally:
                await session.close()
            
            # No results found
            return {
                'title': '',
                'summary': f'No Wikipedia article found for "{query}"',
                'url': f'https://en.wikipedia.org/wiki/Special:Search/{quote(query)}',
                'thumbnail': '',
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Wikipedia search error: {e}")
            return {
                'title': '',
                'summary': f'Error searching Wikipedia: {e}',
                'url': '',
                'thumbnail': '',
                'timestamp': time.time()
            }

    async def search_urban_dictionary(self, term: str) -> Dict[str, any]:
        """Search Urban Dictionary."""
        
        try:
            # Check cache
            cache_key = f"urban:{term}"
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result:
                return cached_result
            
            # Urban Dictionary API
            url = f"https://api.urbandictionary.com/v0/define"
            params = {'term': term}
            
            session = aiohttp.ClientSession()
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        definitions = data.get('list', [])
                        
                        if definitions:
                            # Use top definition
                            top_def = definitions[0]
                            
                            result = {
                                'term': top_def.get('word', term),
                                'definition': top_def.get('definition', ''),
                                'example': top_def.get('example', ''),
                                'author': top_def.get('author', ''),
                                'thumbs_up': top_def.get('thumbs_up', 0),
                                'thumbs_down': top_def.get('thumbs_down', 0),
                                'permalink': top_def.get('permalink', ''),
                                'timestamp': time.time()
                            }
                            
                            self._cache_result(cache_key, result)
                            return result
                        
            finally:
                await session.close()
            
            # No definition found
            return {
                'term': term,
                'definition': f'No definition found for "{term}"',
                'example': '',
                'author': '',
                'thumbs_up': 0,
                'thumbs_down': 0,
                'permalink': f'https://www.urbandictionary.com/define.php?term={quote(term)}',
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Urban Dictionary search error: {e}")
            return {
                'term': term,
                'definition': f'Error searching Urban Dictionary: {e}',
                'example': '',
                'author': '',
                'thumbs_up': 0,
                'thumbs_down': 0,
                'permalink': f'https://www.urbandictionary.com/define.php?term={quote(term)}',
                'timestamp': time.time()
            }

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get result from cache if not expired."""
        
        if key in self.cache:
            cached_item = self.cache[key]
            
            if time.time() - cached_item['timestamp'] < self.cache_ttl:
                return cached_item['data']
            else:
                # Remove expired item
                del self.cache[key]
        
        return None

    def _cache_result(self, key: str, data: Dict):
        """Cache search result."""
        
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
        
        # Limit cache size
        if len(self.cache) > 1000:
            # Remove oldest items
            oldest_keys = sorted(
                self.cache.keys(),
                key=lambda k: self.cache[k]['timestamp']
            )[:100]
            
            for old_key in oldest_keys:
                del self.cache[old_key]
```

## Configuration

### API Integration Settings
```bash
# LLM Integration
LLM_PROVIDER=ollama                               # ollama or openrouter
OLLAMA_HOST=http://localhost:11434                # Ollama server URL
OLLAMA_MODEL=llama3.2                             # Default Ollama model
OPENROUTER_API_KEY=                               # OpenRouter API key
OPENROUTER_MODEL=nousresearch/hermes-3-llama-3.1-405b

# LLM Fallback
LLM_FALLBACK_ENABLED=false                        # Enable multi-provider fallback
LLM_FALLBACK_MODELS=                           # Comma-separated model:provider list

# TTS Integration
TTS_ENGINE=kokoro_api                           # kokoro, kokoro_api, supertonic
KOKORO_API_URL=http://localhost:8880           # Kokoro API URL
SUPERTONIC_API_URL=http://localhost:8890        # Supertonic API URL

# STT Integration
STT_ENGINE=whisper                              # whisper or parakeet
WHISPER_API_URL=http://localhost:8891           # Whisper API URL
PARAKEET_API_URL=http://localhost:8892          # Parakeet API URL

# RVC Integration
RVC_WEBUI_URL=http://localhost:7865             # RVC WebUI URL
RVC_API_KEY=                                   # RVC API key (if required)

# Web Search
WEB_SEARCH_ENABLED=true                           # Enable web search
WEB_SEARCH_ENGINE=duckduckgo                      # Default search engine
WEB_SEARCH_MAX_RESULTS=5                         # Max search results
WEB_SEARCH_RATE_LIMIT_DELAY=2.0                  # Rate limit between requests

# API Configuration
API_REQUEST_TIMEOUT=30                            # Request timeout (seconds)
API_RETRY_ATTEMPTS=3                            # Max retry attempts
API_RETRY_DELAY=1.0                             # Delay between retries

# Caching
API_CACHE_ENABLED=true                           # Enable response caching
API_CACHE_TTL=300                               # Cache TTL (seconds)
API_CACHE_MAX_SIZE=1000                         # Max cache entries

# Rate Limiting
API_RATE_LIMIT_ENABLED=true                       # Enable rate limiting
API_RATE_LIMIT_REQUESTS_PER_MINUTE=60           # Requests per minute
API_RATE_LIMIT_BURST=10                        # Burst allowance
```

## Integration Points

### With Chat System
- **LLM Integration**: All LLM calls through interface abstraction
- **Search Integration**: Web search integrated into context building
- **Fallback Logic**: Automatic provider switching on failures

### With Voice System
- **TTS Integration**: Multiple TTS engines through unified interface
- **STT Integration**: Speech recognition services
- **RVC Integration**: Voice cloning services

### With Memory System
- **Embedding Generation**: Text embeddings for RAG
- **Search Integration**: External search for knowledge retrieval
- **Context Building**: API results integrated into context

## Performance Considerations

### 1. Request Optimization
- **Connection Pooling**: Reuse HTTP connections
- **Request Batching**: Group multiple requests when possible
- **Parallel Requests**: Multiple API calls in parallel

### 2. Caching Strategy
- **Response Caching**: Cache frequently used responses
- **Result Caching**: Cache search and lookup results
- **Smart Invalidation**: Intelligent cache invalidation

### 3. Error Handling
- **Retry Logic**: Exponential backoff for retries
- **Circuit Breakers**: Prevent cascade failures
- **Graceful Degradation**: Fallback to simpler functionality

## Security Considerations

### 1. API Key Management
- **Environment Variables**: All API keys stored in environment
- **Key Rotation**: Support for API key rotation
- **Audit Logging**: Log API key usage for security

### 2. Data Privacy
- **Data Minimization**: Only send necessary data
- **Encryption**: Encrypt sensitive data in transit
- **Compliance**: Follow data protection regulations

### 3. Access Control
- **IP Filtering**: Restrict API access by IP
- **Rate Limiting**: Prevent abuse and overuse
- **Request Validation**: Validate all API requests

## Common Issues and Troubleshooting

### 1. LLM Provider Not Responding
```bash
# Check Ollama service
curl http://localhost:11434/api/tags

# Check model availability
ollama list

# Test with simple request
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2", "prompt": "Hello", "stream": false}'
```

### 2. TTS Service Errors
```python
# Test Kokoro API
import aiohttp
async def test_kokoro():
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8880/voices") as resp:
            print(f"Status: {resp.status}")
            print(f"Response: {await resp.text()}")
```

### 3. Web Search Not Working
```bash
# Test web search API
python -c "
import asyncio
from services.discord.web_search import WebSearchService
async def test():
    service = WebSearchService()
    result = await service.search_web('test query')
    print(result)
asyncio.run(test())
"
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `services/interfaces/llm_interface.py` | Abstract LLM interface |
| `services/llm/ollama.py` | Ollama LLM client |
| `services/llm/openrouter.py` | OpenRouter LLM client |
| `services/llm/fallback.py` | Multi-provider fallback system |
| `services/clients/tts_client.py` | TTS API clients |
| `services/clients/stt_client.py` | STT API clients |
| `services/clients/rvc_client.py` | RVC API clients |
| `services/discord/web_search.py` | Web search integration |

---

**Last Updated**: 2025-12-16
**Version**: 1.0