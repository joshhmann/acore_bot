# Query Optimization System

## Overview

The bot now features an intelligent query optimization system that improves web search results through:
1. **Pattern-based transformation** - Recognizes common query patterns and transforms them optimally
2. **RAG-based learning** - Learns from successful searches to improve future queries
3. **Adaptive refinement** - Gets better over time as it processes more searches

## How It Works

### 1. Pattern Matching
When you ask a question, the bot matches it against known patterns:

**Examples:**
- `"any recent news on halo"` → `"halo news 2024 2025"`
- `"when is gta 6 coming out"` → `"gta 6 release date 2024 2025"`
- `"ps5 vs xbox"` → `"ps5 vs xbox comparison 2024"`
- `"what is ray tracing"` → `"ray tracing explanation definition"`
- `"steam overlay not working"` → `"steam overlay fix troubleshooting solution 2024"`

### 2. Learning System
Every search is recorded with:
- Original query
- Transformed query
- Number of results
- Success/failure

When you ask a similar question later, the bot can reuse successful transformations!

### 3. Categories of Patterns

#### 📰 News Queries
- `"any recent news about X"`
- `"latest updates on X"`
- `"what's new with X"`

#### 🎮 Game-Specific
- `"when is X coming out"`
- `"is X released yet"`
- `"any new X games"`

#### ❓ How-To Queries
- `"how to install X"`
- `"how do I fix X"`

#### ⚖️ Comparisons
- `"X vs Y"`
- `"X versus Y"`

#### 📚 Definitions
- `"what is X"`
- `"explain X"`
- `"define X"`

#### 🔧 Troubleshooting
- `"why won't X work"`
- `"X not working"`
- `"X error"`

## Usage

### Automatic Search
The bot automatically detects when web search is needed and applies optimization:

```
@Arby any recent news on cyberpunk 2077
```

The bot will:
1. Match pattern: "any recent news on X"
2. Transform to: "cyberpunk 2077 news 2024 2025"
3. Search with optimized query
4. Record success for future learning

### Manual Search Command
Force a web search with optimization:

```
/search halo infinite updates
```

### View Statistics
See how well the optimization is working:

```
/search_stats
```

This shows:
- Total queries processed
- Success rate
- Pattern matches vs learned transformations
- Fallback usage

## Configuration

### Pattern File
Edit `/root/acore_bot/data/query_patterns.json` to:
- Add new patterns
- Modify existing transformations
- Add domain-specific patterns

### Example: Adding a Custom Pattern

```json
{
  "pattern": "^(?:latest)\\s+(.+?)\\s+(?:trailer)$",
  "transform": "{topic} official trailer 2024 2025",
  "examples": [
    "latest gta 6 trailer",
    "latest zelda trailer"
  ]
}
```

## Learning Data

Query optimization data is stored in:
- `data/query_optimization/query_history.jsonl`

Each line contains:
```json
{
  "timestamp": "2025-11-20T00:36:00",
  "original_query": "any recent news on halo",
  "transformed_query": "halo news 2024 2025",
  "results_count": 3,
  "success": true,
  "metadata": {
    "category": "news_queries",
    "source": "pattern_match"
  }
}
```

## Benefits

1. **Better Search Results** - Optimized queries return more relevant results
2. **Reduced Hallucinations** - Better results = less need for the AI to make things up
3. **Self-Improving** - System learns from successes
4. **Transparent** - View stats to see how it's performing
5. **Customizable** - Add your own patterns for specific use cases

## Technical Details

### Services
- `services/query_optimizer.py` - Core optimization logic
- `services/web_search.py` - Integration with search
- `data/query_patterns.json` - Pattern definitions

### Key Classes
- `QueryPatternMatcher` - Pattern matching engine
- `QueryOptimizationRAG` - Learning and similarity detection
- `WebSearchService` - Search with optimization

### Flow
1. User asks question
2. `should_search()` determines if web search needed
3. `optimize_query()` applies patterns or learned transformations
4. Search performed with optimized query
5. Results recorded for learning
6. Context provided to AI with explicit instructions

## Future Enhancements

Potential improvements:
- Vector embeddings for better similarity detection
- Category-specific pattern weighting
- A/B testing different transformations
- User feedback integration
- Domain-specific pattern packs (gaming, tech, etc.)

## Troubleshooting

### No Pattern Matches
If queries aren't being optimized:
1. Check `/search_stats` to see current performance
2. Review `data/query_patterns.json` for applicable patterns
3. Add custom patterns for your use case
4. Check logs for pattern matching attempts

### Low Success Rate
If searches are failing:
1. Check the learning data in `data/query_optimization/`
2. Look for common failure patterns
3. Adjust patterns to be more specific
4. Review search engine results directly

### Logs
Monitor optimization with:
```bash
journalctl -u discordbot -f | grep "optimizer\|Query optimization"
```

## Credits

This system uses:
- Regex-based pattern matching
- Jaccard similarity for query comparison
- JSONL for efficient learning data storage
- DuckDuckGo search via the `ddgs` library
