# Web Search Integration

## Overview

Your bot can now **search the internet** to get real-time information and context! This makes it much smarter for current events, facts, and up-to-date information.

## Features

### Automatic Search Detection
The bot automatically detects when it needs to search:

```
User: Who won the Halo World Championship 2024?
Bot: [Automatically searches web]
Bot: DUDE IT WAS TEAM OPTIC GAMING!! THEY CRUSHED IT BRO!!!

User: What's the weather like?
Bot: [Regular response - no search needed]
Bot: IM A BOT BRO I CANT CHECK WEATHER!! BUT U CAN LOOK OUTSIDE LOL!!
```

### Search Triggers
The bot searches when queries contain:
- **Current events**: "who won", "what happened", "latest news"
- **Time references**: "today", "this year", "2024", "2025", "recent"
- **Explicit requests**: "search", "look up", "find out", "google"
- **Question words**: "when is", "when did"

### Two Search Engines

#### 1. DuckDuckGo (Default, Free)
- ✅ No API key needed
- ✅ Privacy-friendly
- ✅ Instant answers
- ✅ Good for general queries
- ⚠️ Limited to instant answers (not full web search)

#### 2. Google Custom Search
- ✅ More comprehensive results
- ✅ Better ranking
- ✅ More reliable for specific queries
- ⚠️ Requires API key and Custom Search Engine ID
- ⚠️ 100 free queries/day, then paid

## Configuration

### Basic Setup (DuckDuckGo)

In `.env`:
```bash
# Enable web search
WEB_SEARCH_ENABLED=true

# Use DuckDuckGo (no API key needed)
WEB_SEARCH_ENGINE=duckduckgo

# Number of results to include in context
WEB_SEARCH_MAX_RESULTS=3
```

That's it! DuckDuckGo works out of the box.

### Google Custom Search Setup

If you want better results:

1. **Get Google API Key**:
   - Go to https://console.cloud.google.com/
   - Create a project
   - Enable "Custom Search API"
   - Create credentials → API key

2. **Create Custom Search Engine**:
   - Go to https://programmablesearchengine.google.com/
   - Create new search engine
   - Search the entire web (or specific sites)
   - Get your Search Engine ID (cx)

3. **Update `.env`**:
```bash
WEB_SEARCH_ENABLED=true
WEB_SEARCH_ENGINE=google
WEB_SEARCH_MAX_RESULTS=5

# Google credentials
GOOGLE_API_KEY=your_api_key_here
GOOGLE_CX_ID=your_search_engine_id_here
```

## Usage Examples

### Current Events
```
User: Who won the Super Bowl 2024?
Bot: [Searches: "Super Bowl 2024 winner"]
Bot: THE KANSAS CITY CHIEFS BRO!! THEY WON AGAINST TEH 49ERS!! SICK GAME!!
```

### Gaming Info
```
User: When is the next Halo game coming out?
Bot: [Searches: "next Halo game release date"]
Bot: DUDE ITS COMING IN 2025!! IM SO HYPED BRO!! ITS GONNA B EPIC!!!
```

### Technical Questions
```
User: What's the latest Python version?
Bot: [Searches: "latest Python version 2024"]
Bot: PYTHON 3.12 IS TEH LATEST BRO!! U SHOULD UPGRADE!!
```

### Fact Checking
```
User: How tall is Master Chief?
Bot: [Searches: "Master Chief height"]
Bot: HES 7 FEET TALL IN HIS ARMOR BRO!! ABSOLUTE UNIT!! SO COOL!!
```

## How It Works

### 1. Query Analysis
```python
User sends message → Bot analyzes if search needed → Decides based on keywords
```

### 2. Web Search
```python
Bot searches web → Gets top 3 results → Extracts titles and snippets
```

### 3. Context Integration
```python
Search results added to AI context:
---
Web search results for 'Halo World Championship 2024':
1. OpTic Gaming Wins Halo World Championship 2024
   OpTic Gaming defeated FaZe Clan 4-2 in the finals...
   Source: halowaypoint.com
2. 2024 HCS World Championship Results
   Full bracket and results from the tournament...
   Source: halo.gg
---
User query: Who won the Halo World Championship 2024?
```

### 4. AI Response
```python
Bot uses search context → Generates informed response → Speaks in character
```

## Integration with User Profiles

The bot can combine web search with user profiles:

```
User A: What's the latest Halo tournament result?
Bot: [Searches and finds OpTic won]
Bot: YO @UserA!! OPTIC GAMING WON THE WORLD CHAMPIONSHIP!!
     U LOVE COMPETITIVE HALO SO I THOUGHT UD WANNA KNOW BRO!! 💙
     @UserB U SHOULD WATCH TEH VODS!! THEY HAD INSANE PLAYS!!
```

The bot:
- Searches for current info
- Remembers UserA loves competitive Halo (from profile)
- Tags relevant users based on their interests
- Shares information enthusiastically (because close friend)

## Performance & Limits

### DuckDuckGo
- **Speed**: ~1-2 seconds per search
- **Rate limit**: None (public API)
- **Cost**: Free
- **Quality**: Good for instant answers, limited for complex queries

### Google Custom Search
- **Speed**: ~0.5-1 second per search
- **Rate limit**: 100 queries/day free, then $5 per 1000 queries
- **Cost**: Free tier, then paid
- **Quality**: Excellent, full web index

### Best Practices

1. **Cache results**: Don't search the same thing twice in 5 minutes
2. **Limit queries**: Only search when really needed
3. **Fallback gracefully**: If search fails, still respond without it
4. **Combine with RAG**: Use local docs for static info, web for current info

## Manual Search Commands (Coming Soon)

```
/search <query> - Manually search and show results
/search_settings - View/change search engine settings
```

## Troubleshooting

### "Web search failed"
- Check internet connection
- Verify API keys (if using Google)
- Check rate limits

### "No results found"
- Query might be too specific
- Try different keywords
- Check if search engine is down

### "Search results not relevant"
- Add more specific keywords
- Try different search engine
- Combine with RAG for better context

## Future Enhancements

- **Multi-search**: Search multiple engines and combine results
- **Image search**: Get relevant images for queries
- **News focus**: Prioritize news sources for current events
- **Source verification**: Check source reliability
- **Caching**: Store recent searches to reduce API calls
- **User preferences**: Let users choose search engine per query

## Privacy

- **DuckDuckGo**: Privacy-focused, doesn't track users
- **Google**: Standard Google tracking applies
- **Your bot**: Doesn't store search queries (unless you add logging)
- **Local only**: All processing happens on your server

## Summary

✅ Bot can search the web for real-time information
✅ Automatic detection - searches when needed
✅ DuckDuckGo (free) or Google (better quality)
✅ Integrates with user profiles for personalized responses
✅ Privacy-friendly with DuckDuckGo
✅ Easy to configure

Now your bot knows about current events, not just its training data!
