# T27: Local NLP Topic Detection

## Overview
The **Topic Detection System** has been upgraded from a simple keyword-based approach (Regex) to a hybrid system that incorporates **Local Semantic NLP**. This allows the bot to understand the "meaning" of messages and detect topics even when specific keywords are missing.

## Key Features

### 1. Hybrid Detection
The system uses a two-stage process for optimal performance and accuracy:
1.  **Fast Path (Regex)**: Instant keyword matching using optimized regex patterns. Catches obvious mentions (e.g., "I like gaming").
2.  **Smart Path (Semantic NLP)**: Uses `sentence-transformers` (all-MiniLM-L6-v2) to compare the semantic meaning of the message against topic descriptions. Catches subtle or conceptual mentions (e.g., "I'm building a neural network" → Technology).

### 2. Semantic Embeddings
- **Model**: `all-MiniLM-L6-v2` (Lightweight, ~80MB, fast on CPU).
- **Reuse**: Reuses the model instance from `LorebookService` to save memory.
- **Rich Descriptions**: Topics are embedded using a combination of their name and their associated keywords (e.g., "technology tech software hardware..."). This provides a dense semantic target for the model.

### 3. Performance
- **Latency**: < 20ms per message (on standard CPU).
- **Pre-computation**: Topic embeddings are generated once at startup.
- **Caching**: Message embeddings are cached by `LorebookService`.

## Configuration
The system is auto-configured.
- **Threshold**: Defaults to `0.35` cosine similarity (tuned for short text matching).
- **Topics**: 17 built-in topics (Gaming, Technology, Movies, etc.).

## Example Cases

| Message | Regex Result | NLP Result | Final Result |
|---------|--------------|------------|--------------|
| "I love gaming" | `gaming` | (Skipped) | `gaming` |
| "CPU usage is high" | (None) | `technology` | `technology` |
| "Adopted a golden retriever"| (None) | `pets` | `pets` |
| "It's raining cats and dogs"| `pets` (False pos?) | `weather` | `weather` (merged) |

## Integration
- **File**: `services/persona/behavior.py`
- **Method**: `_analyze_message_topics`
- **Dependency**: `LorebookService` (for model access)
