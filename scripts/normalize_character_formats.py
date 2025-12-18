#!/usr/bin/env python3
"""Character Format Normalization Script

Scans prompts/characters/ directory for non-standard character card formats
and normalizes them to standardized V2 schema with validated rag_categories.

Features:
- Detects V1, V2, and malformed character cards
- Validates and normalizes rag_categories (lowercase, alphanumeric+underscore only)
- Dry-run mode to preview changes before applying
- Backup original files before modification
"""

import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import shutil
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CharacterFormatNormalizer:
    """Normalize character card formats to standardized V2 schema."""

    def __init__(self, characters_dir: Path, backup_dir: Optional[Path] = None):
        """Initialize normalizer.

        Args:
            characters_dir: Directory containing character JSON files
            backup_dir: Directory for backups (defaults to characters_dir/backups)
        """
        self.characters_dir = Path(characters_dir)
        self.backup_dir = backup_dir or (self.characters_dir / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def detect_format_issues(self, char_file: Path) -> List[str]:
        """Detect format issues in a character file.

        Args:
            char_file: Path to character JSON file

        Returns:
            List of detected issues (empty if file is valid V2)
        """
        issues = []

        try:
            with open(char_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return [f"Invalid JSON: {e}"]
        except Exception as e:
            return [f"Read error: {e}"]

        # Check for V2 spec wrapper
        if "spec" not in data or "data" not in data:
            issues.append("Missing V2 spec wrapper (spec/data keys)")

        # Check data structure
        card_data = data.get("data", data)

        # Check required V2 fields
        required_fields = [
            "name",
            "description",
            "personality",
            "scenario",
            "first_mes",
        ]
        for field in required_fields:
            if field not in card_data:
                issues.append(f"Missing required field: {field}")

        # Check extensions structure
        extensions = card_data.get("extensions", {})
        if not isinstance(extensions, dict):
            issues.append(f"Invalid extensions type: {type(extensions)}")

        knowledge_domain = extensions.get("knowledge_domain", {})
        if not isinstance(knowledge_domain, dict):
            issues.append(f"Invalid knowledge_domain type: {type(knowledge_domain)}")

        # Check rag_categories format
        if "rag_categories" in knowledge_domain:
            cats = knowledge_domain["rag_categories"]
            if not isinstance(cats, list):
                issues.append(f"rag_categories must be list, got {type(cats)}")
            else:
                for i, cat in enumerate(cats):
                    if not isinstance(cat, str):
                        issues.append(
                            f"rag_categories[{i}] must be string, got {type(cat)}"
                        )
                    else:
                        # Check for non-normalized format
                        cat_normalized = cat.lower().strip()
                        if cat != cat_normalized:
                            issues.append(
                                f"rag_categories[{i}] not normalized: '{cat}' should be '{cat_normalized}'"
                            )

                        # Check for invalid characters
                        if not all(c.isalnum() or c == "_" for c in cat_normalized):
                            issues.append(
                                f"rag_categories[{i}] has invalid chars: '{cat}' (only alphanumeric + underscore allowed)"
                            )

        return issues

    def normalize_character(
        self, char_file: Path
    ) -> Tuple[bool, Optional[Dict], List[str]]:
        """Normalize a character file to V2 format.

        Args:
            char_file: Path to character JSON file

        Returns:
            Tuple of (needs_update, normalized_data, issues_fixed)
        """
        try:
            with open(char_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {char_file}: {e}")
            return (False, None, [])

        issues_fixed = []

        # Ensure V2 spec wrapper
        if "spec" not in data or "data" not in data:
            # Wrap in V2 spec
            data = {
                "spec": "chara_card_v2",
                "spec_version": "2.0",
                "data": data if "data" not in data else data["data"],
            }
            issues_fixed.append("Added V2 spec wrapper")

        card_data = data["data"]

        # Ensure required fields exist (with defaults)
        defaults = {
            "name": char_file.stem,
            "description": "",
            "personality": "",
            "scenario": "",
            "first_mes": "",
            "mes_example": "",
            "alternate_greetings": [],
            "system_prompt": "",
            "creator_notes": "",
            "tags": [],
            "creator": "",
            "character_version": "1.0",
        }

        for field, default in defaults.items():
            if field not in card_data:
                card_data[field] = default
                issues_fixed.append(f"Added missing field: {field}")

        # Ensure extensions structure
        if "extensions" not in card_data:
            card_data["extensions"] = {}
            issues_fixed.append("Added extensions structure")

        extensions = card_data["extensions"]
        if not isinstance(extensions, dict):
            card_data["extensions"] = {}
            extensions = card_data["extensions"]
            issues_fixed.append("Fixed extensions type")

        # Ensure knowledge_domain
        if "knowledge_domain" not in extensions:
            extensions["knowledge_domain"] = {}
            issues_fixed.append("Added knowledge_domain")

        knowledge_domain = extensions["knowledge_domain"]
        if not isinstance(knowledge_domain, dict):
            extensions["knowledge_domain"] = {}
            knowledge_domain = extensions["knowledge_domain"]
            issues_fixed.append("Fixed knowledge_domain type")

        # Normalize rag_categories
        if "rag_categories" in knowledge_domain:
            raw_cats = knowledge_domain["rag_categories"]
            if not isinstance(raw_cats, list):
                knowledge_domain["rag_categories"] = []
                issues_fixed.append(
                    f"Fixed rag_categories type from {type(raw_cats)} to list"
                )
                raw_cats = []

            normalized_cats = []
            for cat in raw_cats:
                if not isinstance(cat, str):
                    issues_fixed.append(f"Removed non-string category: {cat}")
                    continue

                cat_normalized = cat.lower().strip()
                if not cat_normalized:
                    issues_fixed.append("Removed empty category")
                    continue

                if not all(c.isalnum() or c == "_" for c in cat_normalized):
                    issues_fixed.append(f"Removed invalid category: '{cat}'")
                    continue

                if cat != cat_normalized:
                    issues_fixed.append(
                        f"Normalized category: '{cat}' -> '{cat_normalized}'"
                    )

                normalized_cats.append(cat_normalized)

            knowledge_domain["rag_categories"] = normalized_cats
        else:
            knowledge_domain["rag_categories"] = []

        data["data"] = card_data

        needs_update = len(issues_fixed) > 0
        return (needs_update, data, issues_fixed)

    def backup_file(self, file_path: Path) -> Path:
        """Create backup of file with timestamp.

        Args:
            file_path: Path to file to backup

        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        logger.info(f"Backed up: {file_path.name} -> {backup_path.name}")

        return backup_path

    def scan_directory(self, dry_run: bool = True) -> Dict[str, List]:
        """Scan directory for format issues.

        Args:
            dry_run: If True, only report issues without modifying files

        Returns:
            Dictionary with scan results
        """
        results = {"scanned": [], "needs_update": [], "already_valid": [], "errors": []}

        json_files = list(self.characters_dir.glob("*.json"))
        logger.info(f"Scanning {len(json_files)} character files...")

        for char_file in json_files:
            results["scanned"].append(char_file.name)

            # Detect issues
            issues = self.detect_format_issues(char_file)

            if not issues:
                results["already_valid"].append(char_file.name)
                logger.info(f"✓ {char_file.name}: Already valid V2 format")
                continue

            # File needs update
            logger.warning(f"⚠ {char_file.name}: {len(issues)} issues detected")
            for issue in issues:
                logger.warning(f"  - {issue}")

            # Attempt normalization
            needs_update, normalized_data, fixes = self.normalize_character(char_file)

            if not needs_update:
                results["already_valid"].append(char_file.name)
                continue

            results["needs_update"].append(
                {
                    "file": char_file.name,
                    "path": char_file,
                    "issues": issues,
                    "fixes": fixes,
                    "normalized_data": normalized_data,
                }
            )

            logger.info(f"  → {len(fixes)} fixes available")
            for fix in fixes:
                logger.info(f"    • {fix}")

            # Apply fixes if not dry-run
            if not dry_run:
                try:
                    # Backup original
                    self.backup_file(char_file)

                    # Write normalized version
                    with open(char_file, "w", encoding="utf-8") as f:
                        json.dump(normalized_data, f, indent=2, ensure_ascii=False)

                    logger.info(f"✓ Updated: {char_file.name}")
                except Exception as e:
                    logger.error(f"✗ Failed to update {char_file.name}: {e}")
                    results["errors"].append({"file": char_file.name, "error": str(e)})

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Normalize character card formats to V2 standard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (preview changes)
  python normalize_character_formats.py

  # Apply changes
  python normalize_character_formats.py --apply

  # Use custom directory
  python normalize_character_formats.py --dir /path/to/characters --apply
        """,
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("./prompts/characters"),
        help="Directory containing character files (default: ./prompts/characters)",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply fixes (default is dry-run mode)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate directory
    if not args.dir.exists():
        logger.error(f"Directory not found: {args.dir}")
        return 1

    # Initialize normalizer
    normalizer = CharacterFormatNormalizer(args.dir)

    # Run scan
    dry_run = not args.apply
    if dry_run:
        logger.info("=== DRY RUN MODE (no files will be modified) ===")
    else:
        logger.info("=== APPLYING FIXES ===")

    results = normalizer.scan_directory(dry_run=dry_run)

    # Print summary
    print("\n" + "=" * 60)
    print("SCAN SUMMARY")
    print("=" * 60)
    print(f"Total files scanned: {len(results['scanned'])}")
    print(f"Already valid V2: {len(results['already_valid'])}")
    print(f"Need updates: {len(results['needs_update'])}")
    print(f"Errors: {len(results['errors'])}")

    if results["needs_update"]:
        print("\nFiles needing updates:")
        for item in results["needs_update"]:
            print(f"  • {item['file']}: {len(item['fixes'])} fixes")

    if results["errors"]:
        print("\nErrors:")
        for item in results["errors"]:
            print(f"  • {item['file']}: {item['error']}")

    if dry_run and results["needs_update"]:
        print("\n💡 Run with --apply to make changes")
    elif not dry_run and results["needs_update"]:
        print(f"\n✅ Updated {len(results['needs_update'])} files")
        print(f"   Backups saved to: {normalizer.backup_dir}")

    return 0


if __name__ == "__main__":
    exit(main())
