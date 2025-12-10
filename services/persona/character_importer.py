"""Character Card Importer - Import SillyTavern V2 PNG character cards."""
import json
import base64
import logging
from pathlib import Path
from typing import Optional, Dict
import struct
import zlib

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
            with open(png_path, 'rb') as f:
                # Verify PNG signature
                signature = f.read(8)
                if signature != b'\x89PNG\r\n\x1a\n':
                    logger.error(f"{png_path} is not a valid PNG file")
                    return None

                # Read chunks
                while True:
                    # Read chunk length and type
                    chunk_header = f.read(8)
                    if len(chunk_header) < 8:
                        break

                    length = struct.unpack('>I', chunk_header[:4])[0]
                    chunk_type = chunk_header[4:8].decode('ascii')

                    # Read chunk data
                    data = f.read(length)
                    crc = f.read(4)  # CRC (unused)

                    # Check for tEXt chunk with 'chara' keyword
                    if chunk_type == 'tEXt':
                        # Format: keyword\x00text
                        null_idx = data.find(b'\x00')
                        if null_idx > 0:
                            keyword = data[:null_idx].decode('latin-1')
                            text = data[null_idx + 1:].decode('latin-1')
                            
                            if keyword == 'chara':
                                # Decode base64
                                try:
                                    json_str = base64.b64decode(text).decode('utf-8')
                                    return json.loads(json_str)
                                except Exception as e:
                                    logger.error(f"Failed to decode chara data: {e}")

                    # Check for iTXt chunk (international text)
                    elif chunk_type == 'iTXt':
                        # More complex format, but try to find 'chara'
                        try:
                            # iTXt: keyword\x00compressionFlag\x00compressionMethod\x00langTag\x00translatedKeyword\x00text
                            parts = data.split(b'\x00', 4)
                            if len(parts) >= 5:
                                keyword = parts[0].decode('utf-8')
                                if keyword == 'chara':
                                    text = parts[4].decode('utf-8')
                                    try:
                                        json_str = base64.b64decode(text).decode('utf-8')
                                        return json.loads(json_str)
                                    except:
                                        # Might not be base64
                                        return json.loads(text)
                        except Exception as e:
                            pass

                    # End of PNG
                    if chunk_type == 'IEND':
                        break

            logger.warning(f"No character data found in {png_path}")
            return None

        except Exception as e:
            logger.error(f"Error reading PNG {png_path}: {e}")
            return None

    def convert_to_internal_format(self, card_data: Dict, png_path: Path) -> Dict:
        """Convert SillyTavern card format to our internal format.
        
        Args:
            card_data: Parsed SillyTavern character data
            png_path: Original PNG path (for avatar)
            
        Returns:
            Character dict in our format
        """
        # Handle both V1 and V2 formats
        if 'data' in card_data:
            # V2 format
            data = card_data['data']
        else:
            # V1 format
            data = card_data

        # Extract name for ID
        name = data.get('name', 'imported_character')
        char_id = name.lower().replace(' ', '_').replace("'", "")
        
        # Build our format
        character = {
            "id": char_id,
            "display_name": name,
            "description": data.get('description', ''),
            "personality": data.get('personality', ''),
            "scenario": data.get('scenario', ''),
            "first_message": data.get('first_mes', ''),
            "example_messages": data.get('mes_example', ''),
            
            # Avatar - copy PNG to characters folder
            "avatar_url": None,  # Will be set after copying
            
            # Extended data
            "system_prompt": data.get('system_prompt', ''),
            "post_history_instructions": data.get('post_history_instructions', ''),
            "creator_notes": data.get('creator_notes', ''),
            "tags": data.get('tags', []),
            
            # Our extensions
            "framework": "neuro",  # Default framework
            "knowledge_domain": {
                "rag_categories": [],
                "lorebooks": []
            },
            "voice": {
                "tts_voice": None,
                "rvc_model": None
            },
            
            # Metadata
            "imported_from": str(png_path.name),
            "source_format": "sillytavern_v2" if 'data' in card_data else "sillytavern_v1"
        }
        
        # Handle character book (embedded lorebook)
        if 'character_book' in data:
            book = data['character_book']
            character['embedded_lorebook'] = book
        
        return character

    def import_card(self, png_path: Path, copy_avatar: bool = True) -> Optional[Path]:
        """Import a character card from PNG.
        
        Args:
            png_path: Path to character PNG
            copy_avatar: Whether to copy the PNG as avatar
            
        Returns:
            Path to created JSON file or None on failure
        """
        png_path = Path(png_path)
        
        if not png_path.exists():
            logger.error(f"File not found: {png_path}")
            return None

        # Extract metadata
        card_data = self.extract_png_metadata(png_path)
        if not card_data:
            logger.error(f"No character data in {png_path}")
            return None

        # Convert to our format
        character = self.convert_to_internal_format(card_data, png_path)
        char_id = character['id']
        
        # Copy avatar if requested
        if copy_avatar:
            avatar_dest = self.characters_dir / f"{char_id}.png"
            import shutil
            shutil.copy(png_path, avatar_dest)
            # Set avatar URL to local path (could also upload to Discord CDN)
            character['avatar_url'] = f"attachment://{char_id}.png"
            logger.info(f"Copied avatar to {avatar_dest}")

        # Save JSON
        json_path = self.characters_dir / f"{char_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(character, f, indent=2, ensure_ascii=False)

        logger.info(f"Imported character: {character['display_name']} -> {json_path}")
        return json_path

    def import_from_directory(self, source_dir: Path) -> list:
        """Import all PNG character cards from a directory.
        
        Args:
            source_dir: Directory containing PNG cards
            
        Returns:
            List of imported character paths
        """
        source_dir = Path(source_dir)
        imported = []
        
        for png_file in source_dir.glob("*.png"):
            result = self.import_card(png_file)
            if result:
                imported.append(result)
        
        logger.info(f"Imported {len(imported)} characters from {source_dir}")
        return imported


# CLI usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python character_importer.py <png_file_or_directory>")
        sys.exit(1)
    
    importer = CharacterCardImporter()
    path = Path(sys.argv[1])
    
    if path.is_dir():
        results = importer.import_from_directory(path)
        print(f"Imported {len(results)} characters")
    else:
        result = importer.import_card(path)
        if result:
            print(f"Imported: {result}")
        else:
            print("Import failed")
