"""Character Card Importer - Import SillyTavern V2 PNG character cards."""

import json
import base64
import logging
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import struct

logger = logging.getLogger(__name__)


class CharacterCardImporter:
    """Import character cards from SillyTavern V2 PNG format."""

    def __init__(self, characters_dir: Path = Path("./prompts/characters")):
        """Initialize importer.

        Args:
            characters_dir: Directory to save imported characters
        """
        self.characters_dir = Path(characters_dir)
        self.characters_dir.mkdir(parents=True, exist_ok=True)

    def extract_png_metadata(self, png_path: Path) -> Optional[Dict]:
        """Extract character data from PNG tEXt/iTXt chunks.

        SillyTavern embeds character JSON in the 'chara' tEXt chunk as base64.

        Args:
            png_path: Path to PNG file

        Returns:
            Character data dict or None if not found
        """
        try:
            with open(png_path, "rb") as f:
                # Verify PNG signature
                signature = f.read(8)
                if signature != b"\x89PNG\r\n\x1a\n":
                    logger.error(f"{png_path} is not a valid PNG file")
                    return None

                # Read chunks
                while True:
                    # Read chunk length and type
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8:
                        break

                    length = struct.unpack(">I", chunk_header[:4])[0]
                    chunk_type = chunk_header[4:8].decode("ascii")

                    # Read chunk data
                    data = f.read(length)
                    f.read(4)  # CRC (unused)

                    # Check for tEXt chunk with 'chara' keyword
                    if chunk_type == "tEXt":
                        # Format: keyword\x00text
                        null_idx = data.find(b"\x00")
                        if null_idx > 0:
                            keyword = data[:null_idx].decode("latin-1")
                            text = data[null_idx + 1 :].decode("latin-1")

                            if keyword == "chara":
                                # Decode base64
                                try:
                                    json_str = base64.b64decode(text).decode("utf-8")
                                    return json.loads(json_str)
                                except Exception as e:
                                    logger.error(f"Failed to decode chara data: {e}")

                    # Check for iTXt chunk (international text)
                    elif chunk_type == "iTXt":
                        # More complex format, but try to find 'chara'
                        try:
                            # iTXt: keyword\x00compressionFlag\x00compressionMethod\x00langTag\x00translatedKeyword\x00text
                            parts = data.split(b"\x00", 4)
                            if len(parts) >= 5:
                                keyword = parts[0].decode("utf-8")
                                if keyword == "chara":
                                    text = parts[4].decode("utf-8")
                                    try:
                                        json_str = base64.b64decode(text).decode(
                                            "utf-8"
                                        )
                                        return json.loads(json_str)
                                    except (Exception,):
                                        # Might not be base64
                                        return json.loads(text)
                        except Exception:
                            pass

                    # End of PNG
                    if chunk_type == "IEND":
                        break

            logger.warning(f"No character data found in {png_path}")
            return None

        except Exception as e:
            logger.error(f"Error reading PNG {png_path}: {e}")
            return None

    def convert_to_internal_format(self, card_data: Dict, png_path: Path) -> Dict:
        """Convert SillyTavern card format to our internal V2 format.

        Detects format variants and always outputs standardized V2 schema with
        extensions.knowledge_domain including validated rag_categories.

        Args:
            card_data: Parsed SillyTavern character data
            png_path: Original PNG path (for avatar)

        Returns:
            Character dict in V2 format with extensions
        """
        # Detect format: V2 has 'spec' and 'data' keys
        if "spec" in card_data and "data" in card_data:
            # Already V2 format
            data = card_data["data"]
            spec = card_data.get("spec", "chara_card_v2")
            spec_version = card_data.get("spec_version", "2.0")
        elif "data" in card_data:
            # V2 format without spec wrapper
            data = card_data["data"]
            spec = "chara_card_v2"
            spec_version = "2.0"
        else:
            # V1 format - needs conversion to V2
            data = card_data
            spec = "chara_card_v2"
            spec_version = "2.0"

        # Extract name for ID
        name = data.get("name", "imported_character")
        name.lower().replace(" ", "_").replace("'", "")

        # Handle extensions - normalize to V2 format
        extensions = data.get("extensions", {})
        knowledge_domain = extensions.get("knowledge_domain", {})

        # Validate and normalize rag_categories
        raw_categories = knowledge_domain.get("rag_categories", [])
        if not isinstance(raw_categories, list):
            logger.warning(
                f"Character {name}: rag_categories must be a list, got {type(raw_categories)}. Resetting to []."
            )
            raw_categories = []

        # Normalize and validate each category
        validated_categories = []
        for cat in raw_categories:
            if not isinstance(cat, str):
                logger.warning(
                    f"Character {name}: Invalid category type {type(cat)}, expected str. Skipping."
                )
                continue

            # Normalize: lowercase and strip whitespace
            cat_normalized = cat.lower().strip()
            if not cat_normalized:
                logger.warning(f"Character {name}: Empty category string. Skipping.")
                continue

            # Validate: only alphanumeric and underscore
            if not all(c.isalnum() or c == "_" for c in cat_normalized):
                logger.warning(
                    f"Character {name}: Invalid category '{cat}'. Only alphanumeric and underscore allowed. Skipping."
                )
                continue

            validated_categories.append(cat_normalized)

        if validated_categories:
            logger.info(
                f"Character {name}: Normalized RAG categories: {validated_categories}"
            )

        # Update knowledge_domain with validated categories
        knowledge_domain["rag_categories"] = validated_categories
        extensions["knowledge_domain"] = knowledge_domain

        # Build standardized V2 format
        v2_data = {
            "name": name,
            "description": data.get("description", ""),
            "personality": data.get("personality", ""),
            "scenario": data.get("scenario", ""),
            "first_mes": data.get("first_mes", ""),
            "mes_example": data.get("mes_example", ""),
            "alternate_greetings": data.get("alternate_greetings", []),
            "system_prompt": data.get("system_prompt", ""),
            "post_history_instructions": data.get("post_history_instructions", ""),
            "creator_notes": data.get("creator_notes", ""),
            "tags": data.get("tags", []),
            "creator": data.get("creator", ""),
            "character_version": data.get("character_version", "1.0"),
            "avatar_url": data.get("avatar_url"),
            "extensions": extensions,
        }

        # Handle character book (embedded lorebook)
        if "character_book" in data:
            v2_data["character_book"] = data["character_book"]

        # Wrap in V2 spec structure
        character = {"spec": spec, "spec_version": spec_version, "data": v2_data}

        return character

    def import_card(
        self, png_path: Path, copy_avatar: bool = True, auto_compile: bool = True
    ):
        """Import a character card from PNG or JSON.

        Args:
            png_path: Path to character PNG or JSON
            copy_avatar: Whether to copy the PNG as avatar
            auto_compile: Whether to automatically compile the character

        Returns:
            Tuple of (json_path, compiled_path, char_id) or None on failure
        """
        png_path = Path(png_path)

        if not png_path.exists():
            logger.error(f"File not found: {png_path}")
            return None

        # Extract metadata (supports both PNG and JSON)
        if png_path.suffix.lower() == ".json":
            with open(png_path, "r", encoding="utf-8") as f:
                card_data = json.load(f)
        else:
            card_data = self.extract_png_metadata(png_path)
            if not card_data:
                logger.error(f"No character data in {png_path}")
                return None

        # Convert to our V2 format with normalization
        character = self.convert_to_internal_format(card_data, png_path)

        # Extract char_id from V2 structure
        name = character["data"]["name"]
        char_id = name.lower().replace(" ", "_").replace("'", "")

        # Security: Sanitize char_id to prevent path traversal
        if (
            not re.match(r"^[a-zA-Z0-9_]+$", char_id)
            or char_id.startswith(".")
            or not char_id
        ):
            logger.error(
                f"Invalid character ID '{char_id}' - contains unsafe characters"
            )
            return None

        # Copy avatar if requested
        if copy_avatar and png_path.suffix.lower() == ".png":
            avatar_dest = self.characters_dir / f"{char_id}.png"
            import shutil

            shutil.copy(png_path, avatar_dest)
            # Set avatar URL to local path
            character["data"]["avatar_url"] = f"attachment://{char_id}.png"
            logger.info(f"Copied avatar to {avatar_dest}")

        # Save JSON in V2 format
        json_path = self.characters_dir / f"{char_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(character, f, indent=2, ensure_ascii=False)

        logger.info(f"Imported character: {character['data']['name']} -> {json_path}")

        # Auto-compile if requested
        compiled_path = None
        if auto_compile:
            try:
                from services.persona.system import PersonaSystem

                persona_system = PersonaSystem(self.characters_dir.parent)
                compiled = persona_system.compile_persona(
                    char_id, framework_id=None, force_recompile=True
                )
                if compiled:
                    compiled_path = (
                        self.characters_dir.parent / "compiled" / f"{char_id}.json"
                    )
                    logger.info(f"Auto-compiled character: {compiled_path}")
                else:
                    logger.warning(f"Auto-compilation failed for {char_id}")
            except Exception as e:
                logger.error(
                    f"Auto-compilation error for {char_id}: {e}", exc_info=True
                )

        return (json_path, compiled_path, char_id)

    def import_from_directory(
        self, source_dir: Path, auto_compile: bool = True
    ) -> List[Tuple[Path, Optional[Path], str]]:
        """Import all PNG/JSON character cards from a directory.

        Args:
            source_dir: Directory containing PNG/JSON cards
            auto_compile: Whether to auto-compile imported characters

        Returns:
            List of imported character result tuples (json_path, compiled_path, char_id)
        """
        source_dir = Path(source_dir)
        imported = []

        # Import both PNG and JSON files
        for file in list(source_dir.glob("*.png")) + list(source_dir.glob("*.json")):
            result = self.import_card(file, auto_compile=auto_compile)
            if result:
                imported.append(result)

        logger.info(f"Imported {len(imported)} characters from {source_dir}")
        return imported


# CLI usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import SillyTavern character cards")
    parser.add_argument(
        "path", help="PNG/JSON file or directory containing character cards"
    )
    parser.add_argument(
        "--compile", action="store_true", help="Auto-compile characters after import"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    importer = CharacterCardImporter()
    path = Path(args.path)

    if path.is_dir():
        results = importer.import_from_directory(path, auto_compile=args.compile)
        print(f"\n✅ Imported {len(results)} characters")
        if results:
            for json_path, compiled_path, char_id in results:
                status = "✓ compiled" if compiled_path else "⚠ not compiled"
                print(f"  • {char_id}: {json_path.name} ({status})")
    else:
        result = importer.import_card(path, auto_compile=args.compile)
        if result:
            json_path, compiled_path, char_id = result
            print(f"\n✅ Imported: {char_id}")
            print(f"  Character file: {json_path}")
            if compiled_path:
                print(f"  Compiled file: {compiled_path}")
        else:
            print("❌ Import failed")
