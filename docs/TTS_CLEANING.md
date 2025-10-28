# TTS Text Cleaning

## Problem Solved

Roleplay models like L3-8B-Stheno output text with formatting that shouldn't be spoken:
- `*sighs*`, `*laughs*` - roleplay actions in asterisks
- 😂😎🔥 - Emojis
- `**bold**`, `_italic_` - Markdown formatting
- `(stage directions)`, `[notes]` - Parenthetical content
- URLs and code blocks

When these get sent to TTS, the voice literally says "asterisk sighs asterisk" or tries to pronounce emoji names!

## Solution

Added `clean_text_for_tts()` function in [utils/helpers.py](utils/helpers.py:176-244) that:

### Removes:
1. **Asterisk actions** - `*sighs*` → ` `
2. **Emojis** - `😂` → ` `
3. **Markdown** - `**bold**` → `bold`
4. **Code blocks** - `` `code` `` → ` `
5. **URLs** - `https://...` → ` `
6. **Parentheses/brackets** - `(aside)` → ` `
7. **Excessive punctuation** - `!!!!!!!` → `!!!`

### Integration

The TTS service ([services/tts.py](services/tts.py:88-95)) now automatically cleans all text before sending to Kokoro or Edge TTS:

```python
# Clean text before TTS - remove emojis, asterisks, markdown, etc.
cleaned_text = clean_text_for_tts(text)
```

This happens automatically for:
- `/speak` commands
- Voice responses in channels
- Auto-reply voice messages

## Examples

### Before Cleaning
```
*Sighs heavily* Good grief, Chief. Your logic is so profoundly flawed...
```
**TTS would say:** "asterisk Sighs heavily asterisk Good grief..."

### After Cleaning
```
Good grief, Chief. Your logic is so profoundly flawed...
```
**TTS says:** "Good grief, Chief. Your logic is so profoundly flawed..."

---

### Before Cleaning
```
LOLOLOL UR SUCH A N00B 😂😂😂 I PWNED U SO HARD!!!!!11 💀💀
```
**TTS would say:** "LOLOLOL UR SUCH A N00B face with tears of joy face with tears of joy..."

### After Cleaning
```
LOLOLOL UR SUCH A N00B  I PWNED U SO HARD!!!
```
**TTS says:** "LOLOLOL UR SUCH A N00B I PWNED U SO HARD"

## Testing

Test the cleaning function:
```bash
.venv311\Scripts\python.exe test_tts_cleaning.py
```

This shows before/after examples of various roleplay formatting.

## Configuration

No configuration needed - cleaning is automatic and always enabled.

If you want to disable it for testing, comment out these lines in [services/tts.py](services/tts.py:88-95):
```python
# cleaned_text = clean_text_for_tts(text)
# Use 'text' instead of 'cleaned_text' below
```

## Customization

To adjust what gets cleaned, edit [utils/helpers.py](utils/helpers.py:176-244):

```python
def clean_text_for_tts(text: str) -> str:
    # Add more patterns or remove patterns you want to keep
    text = re.sub(r'\*[^*]+\*', '', text)  # Remove asterisks
    # ... etc
```

For example, if you want to keep some punctuation emphasis:
- Current: `!!!!` → `!!!`
- More emphasis: Change `r'!{4,}'` to `r'!{6,}'` to allow up to 5 exclamation marks

## Character-Specific Notes

### Master Chief
- Caps and 1337 speak are preserved: `UR`, `TEH`, `N00B`
- Excessive punctuation is limited but not removed: `!!!11` → `!!!`
- This maintains his chaotic typing style while being speakable

### The Arbiter
- Removes `*sighs*`, `*rolls eyes*` etc.
- Keeps proper punctuation and grammar
- Results in clean, articulate speech

Both characters now sound natural in voice without awkward "asterisk" or emoji names!
