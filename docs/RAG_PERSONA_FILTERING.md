# RAG Persona Filtering Guide

## Problem
By default, all characters were accessing ALL RAG documents (including other personas' files).

## Solution
Characters now filter RAG searches to only their designated categories.

---

## Setting Up RAG Categories for a Character

### Step 1: Add `rag_categories` to Character JSON

Edit `prompts/characters/YOUR_CHARACTER.json`:

```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Your Character",
    "description": "...",
    "personality": "...",

    "extensions": {
      "knowledge_domain": {
        "rag_categories": ["character_name", "shared_category"]
      }
    }
  }
}
```

**Examples:**
- Dagoth Ur: `["dagoth"]`
- Jesus Christ: `["jesus", "biblical"]`
- Hal 9000: `["hal9000", "ai_lore"]`
- Stalin: `["stalin", "soviet_history"]`

### Step 2: Create Category Directory

```bash
mkdir -p /root/acore_bot/data/documents/character_name
```

Category names are case-insensitive (matched by `category.lower()`).

### Step 3: Add Documents

Place `.txt` or `.md` files in the category folder:

```bash
/data/documents/
├── dagoth/
│   ├── dagoth_gaming.txt
│   ├── dagoth_pop_culture.txt
│   └── dagoth_villain_problems.txt
├── jesus/
│   ├── parables.txt
│   ├── teachings.txt
│   └── miracles.txt
└── biblical/  # Shared category for all biblical characters
    ├── old_testament_context.txt
    └── jewish_customs.txt
```

### Step 4: Restart Bot

RAG documents are loaded on startup. After adding new categories/files:

```bash
sudo systemctl restart acore_bot
```

Or reload programmatically (if implemented):
```python
await self.rag.reload()
```

---

## How Filtering Works

### Code Flow

1. **Character Selection** (`cogs/chat/main.py:486-497`)
   ```python
   if selected_persona:
       persona_boost = selected_persona.character.display_name
       if hasattr(selected_persona.character, "knowledge_domain"):
           kd = selected_persona.character.knowledge_domain
           cats = kd.get("rag_categories")
           if isinstance(cats, list):
               persona_categories = cats
   ```

2. **RAG Search** (`services/memory/rag.py:242-264`)
   ```python
   # Vector search (ChromaDB)
   where_filter = {"category": {"$in": categories}}
   results = collection.query(where=where_filter)

   # Keyword search (fallback)
   if categories:
       categories_lower = [c.lower() for c in categories]
       if doc["category"] not in categories_lower:
           continue  # Skip this document
   ```

3. **Result:** Only documents in specified categories are retrieved.

---

## Advanced: Shared Categories

Multiple characters can share categories:

```json
// jesus.json
"rag_categories": ["jesus", "biblical"]

// moses.json
"rag_categories": ["moses", "biblical"]

// paul.json
"rag_categories": ["paul", "biblical", "apostolic"]
```

All three access `/data/documents/biblical/`, but each has their own persona-specific folder too.

---

## Debugging

### Check What Categories Are Loaded

```python
# In Python console or log
rag_stats = self.rag.get_stats()
print(rag_stats["categories"])
# Output: {'dagoth': 6, 'jesus': 1, 'biblical': 0}
```

### Test RAG Search

```python
# Search with category filter
results = self.rag.search(
    query="What do you think about gaming?",
    categories=["dagoth"]
)

for r in results:
    print(f"{r['filename']} - {r['category']} - Score: {r['relevance_score']:.2f}")
```

### Check Character's RAG Categories

```python
persona = self.persona_system.load_character("dagoth_ur")
print(persona.knowledge_domain.get("rag_categories"))
# Output: ['dagoth']
```

---

## Migration Checklist

For existing characters:

- [ ] Add `extensions.knowledge_domain.rag_categories` to character JSON
- [ ] Create category directory: `mkdir -p data/documents/CATEGORY`
- [ ] Move/create persona-specific documents
- [ ] Restart bot
- [ ] Test by asking character about content that should/shouldn't be accessible
- [ ] Check logs for "Vector Search" or "Keyword Search" results

---

## Files Modified

- `prompts/characters/dagoth_ur.json` - Added rag_categories
- `prompts/characters/Biblical_Jesus_Christ.json` - Added rag_categories
- `services/persona/system.py:242-244` - Extract knowledge_domain from extensions
- `services/memory/rag.py:399-505` - Added categories filtering to keyword search
- `services/memory/rag.py:293,397` - Pass categories to keyword_search calls
