# User Mention Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER SENDS MESSAGE                            │
│                  "Hey <@123456789>, hello!"                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              _replace_mentions_with_names()                      │
│              (existing function)                                 │
│                                                                   │
│              Converts: <@123456789> → @Blobert                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM PROCESSING                                │
│              Input: "Hey @Blobert, hello!"                       │
│                                                                   │
│              LLM Response: "Hi @Blobert! How are you?"           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              RESPONSE VALIDATION & ENHANCEMENT                   │
│              (ResponseValidator, naturalness, etc.)              │
│                                                                   │
│              response = "Hi @Blobert! How are you?"              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              CREATE SEPARATE VERSIONS                            │
│                                                                   │
│  ┌────────────────────────────┐  ┌──────────────────────────┐   │
│  │  _restore_mentions()       │  │  _clean_for_tts()        │   │
│  │                            │  │                          │   │
│  │  @Blobert → <@123456789>   │  │  @Blobert → Blobert      │   │
│  │                            │  │  <@ID> → Blobert         │   │
│  └────────────┬───────────────┘  └──────────┬───────────────┘   │
│               │                              │                   │
│               ▼                              ▼                   │
│    discord_response:              tts_response:                  │
│    "Hi <@123456789>! How are you?" "Hi Blobert! How are you?"   │
└───────────────┬──────────────────────────────┬──────────────────┘
                │                              │
                ▼                              ▼
┌───────────────────────────┐    ┌────────────────────────────────┐
│   DISCORD TEXT CHANNEL    │    │    TTS VOICE CHANNEL           │
│                           │    │                                │
│   Sends: discord_response │    │    Speaks: tts_response        │
│                           │    │                                │
│   User sees:              │    │    User hears:                 │
│   "Hi <@123456789>!"      │    │    "Hi Blobert!"               │
│   (clickable blue tag)    │    │    (natural pronunciation)     │
└───────────────────────────┘    └────────────────────────────────┘
```

## Key Points

1. **Input**: Discord mentions (`<@user_id>`) are converted to `@Username` for LLM
2. **LLM Output**: LLM responds with `@Username` (natural format)
3. **Processing**: Create two versions of the response:
   - **Discord version**: `@Username` → `<@user_id>` (clickable)
   - **TTS version**: Any mentions → natural names (pronounceable)
4. **Output**: 
   - Discord gets clickable mentions
   - TTS gets natural pronunciation
   - History stores Discord version (proper format)

## Example Scenarios

### Scenario 1: LLM outputs @Username
```
LLM:      "Hey @Blobert, nice to see you!"
Discord:  "Hey <@123456789>, nice to see you!" ← clickable
TTS:      "Hey Blobert, nice to see you!"     ← natural
```

### Scenario 2: LLM outputs <@user_id> (edge case)
```
LLM:      "Hey <@123456789>, nice to see you!"
Discord:  "Hey <@123456789>, nice to see you!" ← already correct
TTS:      "Hey Blobert, nice to see you!"     ← converted
```

### Scenario 3: Multiple mentions
```
LLM:      "@Blobert and @Robert are both here!"
Discord:  "<@123456789> and <@987654321> are both here!" ← clickable
TTS:      "Blobert and Robert are both here!"           ← natural
```
