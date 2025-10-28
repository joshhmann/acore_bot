# Date/Time Context System

## Problem Solved

Bot now knows the current time and date automatically!

**Before:**
```
User: What time is it?
Bot: I'm sorry, I don't have access to the current time.
```

**After:**
```
User: What time is it?
Bot: YO ITS 3:45 PM BRO!! FRIDAY AFTERNOON!! PERFECT TIME 4 GAMING!!
```

## How It Works

Every time the AI generates a response, it automatically receives:

```
[Current time: 03:45 PM, Date: Friday, October 26, 2025]

[Your persona prompt...]
```

The AI can now answer:
- "What time is it?" → Knows exact time
- "What day is today?" → Knows it's Friday
- "What's the date?" → October 26, 2025
- "Is it morning or evening?" → Can tell from time
- "What month are we in?" → October

## What's Injected

### Compact Context (Default)
```
[Current time: 03:45 PM, Date: Friday, October 26, 2025]
```

Prepended to every system prompt automatically.

### Full Context (Optional)
```
=== SYSTEM CONTEXT ===
Current Date & Time:
- Local Time: 03:45:23 PM
- Date: Friday, October 26, 2025
- Day of Week: Friday
- Month: October
- Year: 2025
- UTC Time: 10:45:23 PM UTC
- Unix Timestamp: 1745673923
===================
```

Can be enabled for more detailed time awareness.

## Example Conversations

### Time Questions
```
User: What time is it?
Chief: YO ITS 3:45 PM BRO!! STILL GOT HOURS 2 PWN N00BS!!

User: Is it too late to play?
Arbiter: It's 11:30 PM. I'd say it's getting rather late, but if you must...
```

### Date Questions
```
User: What day is it?
Chief: ITS FRIDAY DUDE!! WEEKEND ALMOST HEAR!! GAME TIME!!

User: What's today's date?
Arbiter: It's Friday, October 26th, 2025.
```

### Relative Time
```
User: Is it morning?
Chief: NAH BRO ITS 3 PM!! AFTERNOON!! MORNING WAS LIKE 6 HOURS AGO LOL

User: Is it time for lunch?
Arbiter: It's nearly 4 PM, I'd say you've rather missed lunch.
```

## Technical Details

### File: `utils/system_context.py`

Provides:
- `get_datetime_context()` - Full date/time info
- `get_system_context()` - System resource info
- `get_compact_context()` - One-line time/date
- `get_full_context()` - Everything

### Integration: `cogs/chat.py`

Before sending to AI:
```python
# Inject current time/date
context_injected_prompt = f"{SystemContextProvider.get_compact_context()}\n\n{self.system_prompt}"

# AI now knows the time!
response = await self.ollama.chat(history, system_prompt=context_injected_prompt)
```

## Configuration

No configuration needed! It just works.

**To disable** (if you want):
Comment out the injection in `cogs/chat.py`:
```python
# Don't inject time
# context_injected_prompt = f"{SystemContextProvider.get_compact_context()}\n\n{self.system_prompt}"
response = await self.ollama.chat(history, system_prompt=self.system_prompt)
```

## Future Enhancements

### 1. System Status
Enable full context to include:
- CPU usage
- RAM usage
- Disk space
- Platform info

```python
context = SystemContextProvider.get_full_context(include_system=True)
```

Bot can then answer:
- "How's the server doing?"
- "Is the CPU overloaded?"
- "How much RAM is available?"

### 2. Weather Integration
Add weather API:
```python
weather = get_weather(location)
context += f"\nWeather: {weather}"
```

### 3. Calendar Events
Integrate Google Calendar:
```python
events = get_today_events()
context += f"\nToday's events: {events}"
```

### 4. Time Zone Support
Different users, different zones:
```python
user_timezone = get_user_timezone(user_id)
context = get_datetime_context(timezone=user_timezone)
```

## Character-Specific Responses

### Master Chief
```
User: What time is it?
Chief: YO ITS [time]!! [time-appropriate comment]!!

Examples:
- 2 AM: "DUDE Y R U UP SO LATE?? GO 2 SLEEP BRO!!"
- 10 AM: "MORNING BRO!! TIME 2 GAME!!"
- 3 PM: "AFTERNOON DUDE!! PERFECT GAMING TIME!!"
- 11 PM: "ITS LATE BUT WHO CARES!! LETS PLAY!!"
```

### The Arbiter
```
User: What time is it?
Arbiter: It's [time]. [time-appropriate observation].

Examples:
- 2 AM: "It's 2 AM. Shouldn't you be sleeping?"
- 10 AM: "It's 10 in the morning. A reasonable hour."
- 3 PM: "It's mid-afternoon. Time for tea, perhaps?"
- 11 PM: "It's getting rather late, don't you think?"
```

## Testing

```bash
# Test in Python
python -c "from utils.system_context import SystemContextProvider; print(SystemContextProvider.get_compact_context())"

# Output:
[Current time: 03:45 PM, Date: Friday, October 26, 2025]
```

```bash
# Test full context
python -c "from utils.system_context import SystemContextProvider; print(SystemContextProvider.get_full_context())"
```

## Dependencies

```bash
# Already installed:
- datetime (built-in)
- platform (built-in)

# May need to install:
pip install psutil  # For system stats
```

## Summary

✅ Bot knows current time automatically
✅ Bot knows current date automatically
✅ No configuration needed
✅ Works with all personas
✅ Compact overhead (one line)
✅ Can be expanded for more context

Never again will your bot say "I don't know what time it is"!
