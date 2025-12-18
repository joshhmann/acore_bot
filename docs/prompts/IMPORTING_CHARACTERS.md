# Importing Characters Guide

## Overview

The character import system allows you to easily add new AI personalities to your bot from SillyTavern character cards (PNG or JSON format). The system automatically normalizes formats, validates data, and hot-reloads characters without requiring a bot restart.

## Quick Start (3 Steps)

1. **Get character cards** - Download PNG or JSON files from SillyTavern
2. **Import using Discord** - Upload file with `/import_character` command
3. **Start chatting** - Character is immediately active and can be mentioned by name

That's it! The bot handles all the technical details automatically.

---

## Discord Commands

### `/import_character` - Import Single Character

Import a character card from a file attachment.

**Usage:**
```
/import_character file:character.png
```

**What it does:**
- Downloads the attached file
- Detects format (PNG with metadata or JSON)
- Normalizes to V2 standard format
- Validates and fixes `rag_categories`
- Auto-compiles the character
- Hot-reloads the persona system
- Makes character immediately active

**Example:**
```
User: /import_character file:my_character.png

Bot: ✅ Successfully imported "My Character"!
📁 Saved to: prompts/characters/my_character.json
🔧 Compiled: prompts/compiled/my_character.json
🎯 Ready to use! Mention "My Character" to chat.
```

### `!import_folder` - Batch Import

Import all character cards from the `data/import_cards/` directory.

**Usage:**
```
!import_folder
```

**Setup:**
1. Place PNG/JSON files in `data/import_cards/`
2. Run the command
3. All files are imported with auto-compilation

**Example:**
```
User: !import_folder

Bot: 📁 Importing from data/import_cards/...
✅ Imported 3 characters:
   • Character One (character_one.png)
   • Character Two (character_two.json)  
   • Character Three (character_three.png)
🔄 Hot-reloading persona system...
✅ All characters are now active!
```

### `!reload_characters` - Hot-Reload All Characters

Reload all characters from disk without restarting the bot.

**Usage:**
```
!reload_characters
```

**What it shows:**
- Before/after character count
- List of new characters
- List of currently active characters

**Example:**
```
User: !reload_characters

Bot: 🔄 Reloading all characters...
✅ Reload complete!
📊 Before: 9 characters
📊 After: 11 characters
🆕 New: New Character, Another Character
🎯 Active: Dagoth Ur, Scav, Zenos, Maury, HAL 9000, Toad, JC, Toadette, Joseph Stalin, New Character, Another Character
```

---

## CLI Usage

### Import Single Character

```bash
# Basic import
python services/persona/character_importer.py character.png

# Import with auto-compilation
python services/persona/character_importer.py character.png --compile

# Verbose output
python services/persona/character_importer.py character.png --compile --verbose
```

### Batch Import Directory

```bash
# Import all cards from directory
python services/persona/character_importer.py /path/to/cards/

# With auto-compilation and verbose output
python services/persona/character_importer.py /path/to/cards/ --compile --verbose
```

### Available Flags

| Flag | Description |
|------|-------------|
| `--compile` | Auto-compile character after import |
| `--verbose` | Show detailed processing information |
| `--help` | Show all available options |

---

## Format Normalization

The import system automatically converts all character cards to the standardized V2 format.

### What Gets Fixed

1. **V2 Structure** - Wraps old formats in proper V2 schema
2. **RAG Categories** - Validates and normalizes `rag_categories`
3. **Field Mapping** - Maps old field names to new standard
4. **Missing Fields** - Adds required V2 fields with defaults

### RAG Category Validation

```python
# Before (invalid)
"rag_categories": ["Dagoth", "Elder Scrolls!", "  Morrowind  "]

# After (normalized and validated)
"rag_categories": ["dagoth", "morrowind"]
```

**Rules:**
- Convert to lowercase
- Strip whitespace
- Only alphanumeric + underscore allowed
- Invalid entries are removed with warnings

### V2 Standard Structure

```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Character Name",
    "description": "Physical description and background",
    "personality": "Personality traits and behaviors",
    "scenario": "Current situation/context",
    "first_mes": "Default greeting",
    "mes_example": "Example dialogue exchanges",
    "alternate_greetings": ["Alt 1", "Alt 2"],
    "extensions": {
      "knowledge_domain": {
        "rag_categories": ["validated", "normalized"]
      }
    }
  }
}
```

---

## Migration Guide

### Normalizing Existing Characters

If you have existing character files that need normalization, use the migration script.

```bash
# Preview changes (dry run)
python scripts/normalize_character_formats.py

# Apply fixes
python scripts/normalize_character_formats.py --apply

# Custom directory with verbose output
python scripts/normalize_character_formats.py --dir /custom/path --apply --verbose
```

### What the Migration Script Does

1. **Scans** all character files in `prompts/characters/`
2. **Detects** format issues and validation problems
3. **Creates backups** in `prompts/characters/backups/`
4. **Normalizes** to V2 standard format
5. **Validates** and fixes `rag_categories`
6. **Reports** all changes made

### Example Migration Output

```
⚠ dagoth_ur.json: 2 issues detected
  - rag_categories[0] not normalized: 'Dagoth' should be 'dagoth'
  - rag_categories[1] has invalid chars: 'Elder Scrolls!'
  → 2 fixes available
    • Normalized category: 'Dagoth' -> 'dagoth'
    • Removed invalid category: 'Elder Scrolls!'

SCAN SUMMARY
===========
Total files scanned: 12
Already valid V2: 10
Need updates: 2
Errors: 0

💡 Run with --apply to make changes
```

---

## Batch Import Workflow

### Step 1: Prepare Cards

1. Download character cards (PNG or JSON)
2. Place them in `data/import_cards/`
3. Ensure files have clear names (optional but recommended)

```
data/import_cards/
├── character_one.png
├── character_two.json
└── character_three.png
```

### Step 2: Import

Use Discord command for easiest import:

```
!import_folder
```

Or use CLI for more control:

```bash
python services/persona/character_importer.py data/import_cards/ --compile --verbose
```

### Step 3: Verify

Check that characters are loaded:

```
!reload_characters
```

### Step 4: Test

Try mentioning a new character:

```
User: Hey Character One, what do you think about this?

Character One: [Responds in character]
```

---

## Troubleshooting

### Common Issues and Solutions

#### ❌ "Invalid character card format"

**Problem:** The file isn't a valid character card
**Solution:** 
- Ensure PNG files have embedded metadata (SillyTavern export)
- Check JSON files have proper V2 structure
- Use `--verbose` flag to see parsing details

#### ❌ "No rag_categories found"

**Problem:** Character doesn't have RAG categories defined
**Solution:** 
- This is just a warning, not an error
- Character will still work without RAG filtering
- Add `extensions.knowledge_domain.rag_categories` to enable RAG

#### ❌ "Character already exists"

**Problem:** Trying to import a character with duplicate name
**Solution:**
- Rename the file before importing
- Or edit the character's `name` field
- The system uses the `name` field, not filename

#### ❌ "Failed to compile character"

**Problem:** Character imported but compilation failed
**Solution:**
- Check the character JSON for syntax errors
- Ensure all required fields are present
- Run `!reload_characters` to retry compilation

#### ❌ "Character not responding to mentions"

**Problem:** Character imported but not active
**Solution:**
- Check if character is in `ACTIVE_PERSONAS` list in `config.py`
- Run `!reload_characters` to refresh the persona system
- Verify you're using the exact character name for mentions

### Debug Mode

Use verbose logging to troubleshoot issues:

```bash
python services/persona/character_importer.py character.png --compile --verbose
```

This will show:
- Format detection results
- Normalization steps
- Validation warnings
- Compilation status

---

## Security Considerations

### File Validation

The import system includes several security measures:

1. **Path Validation** - Only allows imports from safe directories
2. **File Type Checking** - Only processes PNG and JSON files
3. **Size Limits** - Rejects excessively large files
4. **Content Sanitization** - Validates and sanitizes character data

### Protected Paths

The system restricts file operations to these safe directories:
- `prompts/characters/` - Final character storage
- `data/import_cards/` - Staging area for imports
- `prompts/compiled/` - Compiled persona storage

### Data Sanitization

- **RAG Categories** - Only alphanumeric + underscore allowed
- **Character Names** - Length limits and character restrictions
- **File Names** - Safe filename generation
- **JSON Validation** - Prevents malformed data injection

### Recommendations

1. **Source Verification** - Only import character cards from trusted sources
2. **Review Content** - Check character data before importing
3. **Backup Regularly** - The system creates backups, but keep your own
4. **Monitor Imports** - Use verbose mode to review what's being imported

---

## File Locations

### Input Locations
- `data/import_cards/` - Staging area for batch imports
- Discord file attachments - For single imports

### Output Locations
- `prompts/characters/` - Final character storage (JSON format)
- `prompts/compiled/` - Compiled personas for active use
- `prompts/characters/backups/` - Automatic backups during migration

### Configuration
- `config.py` - `ACTIVE_PERSONAS` list for enabling characters
- `.env` - Bot configuration settings

---

## Advanced Usage

### Custom Import Directory

Use a custom directory for imports:

```bash
python services/persona/character_importer.py /custom/path/ --compile
```

### Selective Compilation

Import without auto-compilation (compile later manually):

```bash
python services/persona/character_importer.py character.png
# Later:
python -c "from services.persona.system import PersonaSystem; PersonaSystem().compile_persona('character_id')"
```

### Programmatic Import

Use the importer directly in Python:

```python
from services.persona.character_importer import CharacterCardImporter
from pathlib import Path

importer = CharacterCardImporter()
json_path, compiled_path, char_id = importer.import_card(
    Path("character.png"),
    copy_avatar=True,
    auto_compile=True
)
print(f"Imported {char_id} to {json_path}")
```

---

## Summary

The character import system provides:

✅ **Easy Import** - Drag-and-drop character cards
✅ **Format Flexibility** - Handles PNG and JSON, any version
✅ **Auto-Normalization** - Fixes format issues automatically  
✅ **Hot-Reload** - No bot restart required
✅ **Validation** - Secure and reliable imports
✅ **Batch Processing** - Import multiple characters at once
✅ **Migration Tools** - Update existing characters easily

You can now expand your bot's personality roster with just a few clicks! 🎭✨