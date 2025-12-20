#!/usr/bin/env python3
"""
Migration script for T5: Persona Memory Isolation

Migrates existing user profiles from flat structure to persona-scoped structure:
  OLD: data/profiles/user_{user_id}.json
  NEW: data/profiles/default/user_{user_id}.json

Features:
- Dry-run mode for safe testing
- Automatic backup creation
- Rollback capability on error
- Progress reporting
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProfileMigrator:
    """Handles migration of user profiles to persona-scoped directories."""

    def __init__(
        self,
        profiles_dir: Path,
        default_persona: str = "default",
        dry_run: bool = False,
    ):
        """Initialize migrator.

        Args:
            profiles_dir: Base profiles directory (e.g., data/profiles)
            default_persona: Persona ID to migrate profiles to
            dry_run: If True, only simulate migration without making changes
        """
        self.profiles_dir = Path(profiles_dir)
        self.default_persona = default_persona
        self.dry_run = dry_run
        self.backup_dir = None

        # Migration stats
        self.files_to_migrate = []
        self.files_migrated = 0
        self.files_skipped = 0
        self.errors = []

    def discover_profiles(self) -> List[Path]:
        """Find all user profile files in the flat structure.

        Returns:
            List of profile file paths to migrate
        """
        if not self.profiles_dir.exists():
            logger.warning(f"Profiles directory does not exist: {self.profiles_dir}")
            return []

        # Find all user_*.json files in the root profiles directory
        # Exclude any that are already in subdirectories
        profiles = []
        for profile_file in self.profiles_dir.glob("user_*.json"):
            # Skip if it's in a subdirectory (already migrated)
            if profile_file.parent != self.profiles_dir:
                continue
            profiles.append(profile_file)

        logger.info(f"Found {len(profiles)} profile(s) to migrate")
        return profiles

    def create_backup(self) -> Path:
        """Create backup of profiles directory.

        Returns:
            Path to backup directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = self.profiles_dir.parent / f"profiles_backup_{timestamp}"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create backup at: {self.backup_dir}")
            return self.backup_dir

        logger.info(f"Creating backup at: {self.backup_dir}")
        shutil.copytree(self.profiles_dir, self.backup_dir)
        logger.info("Backup created successfully")

        return self.backup_dir

    def migrate_file(self, source_file: Path) -> Tuple[bool, str]:
        """Migrate a single profile file.

        Args:
            source_file: Source profile file path

        Returns:
            Tuple of (success, message)
        """
        try:
            # Determine destination path
            dest_dir = self.profiles_dir / self.default_persona
            dest_file = dest_dir / source_file.name

            # Check if already exists
            if dest_file.exists():
                msg = f"Skipping {source_file.name} - already exists at destination"
                logger.warning(msg)
                return False, msg

            # Validate JSON before migrating
            try:
                with open(source_file, "r", encoding="utf-8") as f:
                    profile_data = json.load(f)
                    # Basic validation
                    if "user_id" not in profile_data:
                        msg = f"Invalid profile {source_file.name} - missing user_id"
                        logger.error(msg)
                        return False, msg
            except json.JSONDecodeError as e:
                msg = f"Invalid JSON in {source_file.name}: {e}"
                logger.error(msg)
                return False, msg

            if self.dry_run:
                logger.info(
                    f"[DRY RUN] Would migrate: {source_file.name} -> {dest_file}"
                )
                return True, "Would migrate (dry run)"

            # Create destination directory
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Copy file to new location
            shutil.copy2(source_file, dest_file)
            logger.info(f"Migrated: {source_file.name} -> {dest_file}")

            # Verify copy succeeded
            if not dest_file.exists():
                msg = f"Migration failed - destination file not found: {dest_file}"
                logger.error(msg)
                return False, msg

            # Verify file contents match
            with open(dest_file, "r", encoding="utf-8") as f:
                migrated_data = json.load(f)

            if migrated_data != profile_data:
                msg = f"Migration failed - file contents don't match: {dest_file}"
                logger.error(msg)
                return False, msg

            # Only remove source after successful verification
            if not self.dry_run:
                source_file.unlink()
                logger.debug(f"Removed original file: {source_file}")

            return True, "Migrated successfully"

        except Exception as e:
            msg = f"Error migrating {source_file.name}: {e}"
            logger.error(msg)
            return False, msg

    def migrate_all(self) -> bool:
        """Migrate all discovered profiles.

        Returns:
            True if all migrations succeeded, False otherwise
        """
        # Discover profiles
        self.files_to_migrate = self.discover_profiles()

        if not self.files_to_migrate:
            logger.info("No profiles to migrate")
            return True

        # Create backup
        self.create_backup()

        # Migrate each file
        logger.info(f"Starting migration of {len(self.files_to_migrate)} profile(s)...")

        for profile_file in self.files_to_migrate:
            success, message = self.migrate_file(profile_file)

            if success:
                self.files_migrated += 1
            else:
                self.files_skipped += 1
                self.errors.append((profile_file.name, message))

        # Report results
        self._print_summary()

        return len(self.errors) == 0

    def rollback(self):
        """Rollback migration using backup."""
        if not self.backup_dir or not self.backup_dir.exists():
            logger.error("No backup found - cannot rollback")
            return False

        if self.dry_run:
            logger.info("[DRY RUN] Would rollback from backup")
            return True

        logger.warning("Rolling back migration...")

        # Remove persona subdirectory if it exists
        persona_dir = self.profiles_dir / self.default_persona
        if persona_dir.exists():
            shutil.rmtree(persona_dir)

        # Restore from backup
        for backup_file in self.backup_dir.glob("user_*.json"):
            dest_file = self.profiles_dir / backup_file.name
            shutil.copy2(backup_file, dest_file)
            logger.debug(f"Restored: {backup_file.name}")

        logger.info("Rollback completed")
        return True

    def _print_summary(self):
        """Print migration summary."""
        logger.info("=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total profiles found: {len(self.files_to_migrate)}")
        logger.info(f"Successfully migrated: {self.files_migrated}")
        logger.info(f"Skipped: {self.files_skipped}")
        logger.info(f"Errors: {len(self.errors)}")

        if self.errors:
            logger.error("\nErrors encountered:")
            for filename, error in self.errors:
                logger.error(f"  - {filename}: {error}")

        if self.backup_dir:
            logger.info(f"\nBackup location: {self.backup_dir}")

        if self.dry_run:
            logger.info("\n[DRY RUN] No changes were made")

        logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate user profiles to persona-scoped structure"
    )
    parser.add_argument(
        "--profiles-dir",
        type=str,
        default="data/profiles",
        help="Base profiles directory (default: data/profiles)",
    )
    parser.add_argument(
        "--persona",
        type=str,
        default="default",
        help="Persona ID to migrate to (default: default)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without making changes",
    )
    parser.add_argument(
        "--rollback", action="store_true", help="Rollback last migration using backup"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create migrator
    migrator = ProfileMigrator(
        profiles_dir=Path(args.profiles_dir),
        default_persona=args.persona,
        dry_run=args.dry_run,
    )

    # Execute
    try:
        if args.rollback:
            # Find most recent backup
            backup_dirs = sorted(
                Path(args.profiles_dir).parent.glob("profiles_backup_*"), reverse=True
            )
            if not backup_dirs:
                logger.error("No backup found to rollback from")
                sys.exit(1)

            migrator.backup_dir = backup_dirs[0]
            logger.info(f"Using backup: {migrator.backup_dir}")
            success = migrator.rollback()
        else:
            success = migrator.migrate_all()

        if success:
            logger.info("✓ Migration completed successfully")
            sys.exit(0)
        else:
            logger.error("✗ Migration completed with errors")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\nMigration interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
