#!/usr/bin/env python3
"""Import existing JSON chat history into RL training database.

Converts chat history from JSON files to SQLite format for offline RL pre-training.

Usage:
    python scripts/import_chat_history_to_rl.py
    python scripts/import_chat_history_to_rl.py --chat-history-dir data/chat_history --output data/conversations.db
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the database schema for RL training."""
    cursor = conn.cursor()

    # Create messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            username TEXT,
            user_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create rewards table (for calculated RL rewards)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rewards (
            message_id INTEGER PRIMARY KEY,
            quality_score REAL DEFAULT 0.5,
            reward REAL DEFAULT 0.0,
            action_taken INTEGER DEFAULT 0,
            FOREIGN KEY (message_id) REFERENCES messages(id)
        )
    """)

    conn.commit()
    logger.info("Database schema created")


def calculate_quality_score(message: Dict) -> float:
    """Calculate a simple quality score for a message.

    Args:
        message: Message dictionary with content and metadata

    Returns:
        Quality score between 0.0 and 1.0
    """
    content = message.get("content", "")

    # Basic quality heuristics
    score = 0.5  # Start neutral

    # Longer messages often have more substance (up to a point)
    content_length = len(content)
    if content_length > 20:
        score += 0.1
    if content_length > 50:
        score += 0.1
    if content_length > 100:
        score += 0.1
    if content_length > 500:  # Too long might be spam
        score -= 0.1

    # Check for engagement indicators
    if "?" in content:  # Questions show engagement
        score += 0.1
    if any(
        word in content.lower()
        for word in ["thanks", "thank", "helpful", "good", "nice"]
    ):
        score += 0.1

    # Penalize very short responses
    if content_length < 5:
        score -= 0.2

    return max(0.0, min(1.0, score))


def calculate_reward(message: Dict, prev_message: Optional[Dict] = None) -> float:
    """Calculate RL reward for a message.

    Args:
        message: Current message
        prev_message: Previous message in conversation

    Returns:
        Reward value between -10 and 10
    """
    content = message.get("content", "")
    role = message.get("role", "")

    # Start with neutral reward
    reward = 0.0

    if role == "assistant":
        # Bot messages - reward based on engagement
        if "?" in content:  # Asking questions
            reward += 1.0
        if len(content) > 50:  # Substantial response
            reward += 0.5
        if prev_message and len(content) > len(prev_message.get("content", "")):
            reward += 0.3  # Expanded on previous message

        # Simple sentiment indicators
        positive_words = [
            "good",
            "great",
            "awesome",
            "nice",
            "thanks",
            "helpful",
            "love",
            "perfect",
        ]
        negative_words = [
            "bad",
            "terrible",
            "awful",
            "hate",
            "stupid",
            "dumb",
            "useless",
        ]

        content_lower = content.lower()
        for word in positive_words:
            if word in content_lower:
                reward += 0.5
        for word in negative_words:
            if word in content_lower:
                reward -= 1.0
    else:
        # User messages - used for context, low reward
        reward = 0.1

    return max(-10.0, min(10.0, reward))


def determine_action(message: Dict, prev_message: Optional[Dict] = None) -> int:
    """Determine what RL action the bot took.

    Args:
        message: Current message
        prev_message: Previous message

    Returns:
        Action index (0=WAIT, 1=REACT, 2=ENGAGE, 3=INITIATE)
    """
    role = message.get("role", "")

    if role != "assistant":
        return 0  # Not a bot action

    if prev_message is None:
        return 3  # INITIATE - first message

    prev_role = prev_message.get("role", "")
    content = message.get("content", "")

    if prev_role == "user":
        # Responding to user
        if len(content) < 20:
            return 1  # REACT - short response
        else:
            return 2  # ENGAGE - substantive response
    else:
        return 3  # INITIATE - continuing conversation


def import_chat_history(
    chat_history_dir: Path,
    output_db: Path,
    min_quality: float = 0.3,
) -> int:
    """Import chat history from JSON files to SQLite.

    Args:
        chat_history_dir: Directory containing JSON chat history files
        output_db: Output SQLite database path
        min_quality: Minimum quality score to include

    Returns:
        Number of transitions imported
    """
    # Create output directory
    output_db.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(output_db)
    create_schema(conn)
    cursor = conn.cursor()

    total_messages = 0
    total_transitions = 0

    # Process each chat history file
    for json_file in sorted(chat_history_dir.glob("*.json")):
        channel_id = int(json_file.stem)
        logger.info(f"Processing {json_file.name} (channel {channel_id})")

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load {json_file}: {e}")
            continue

        if not messages:
            continue

        # Insert messages and calculate rewards
        prev_message = None
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            role = msg.get("role", "")
            username = msg.get("username", "")
            user_id = msg.get("user_id", 0)

            # Calculate quality and reward
            quality = calculate_quality_score(msg)

            # Skip low quality messages
            if quality < min_quality:
                prev_message = msg
                continue

            reward = calculate_reward(msg, prev_message)
            action = determine_action(msg, prev_message)

            # Insert message
            cursor.execute(
                """
                INSERT INTO messages (channel_id, role, content, username, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (channel_id, role, content, username, user_id),
            )
            message_id = cursor.lastrowid

            # Insert reward record
            cursor.execute(
                """
                INSERT INTO rewards (message_id, quality_score, reward, action_taken)
                VALUES (?, ?, ?, ?)
                """,
                (message_id, quality, reward, action),
            )

            total_messages += 1

            # Count transitions (pairs of messages)
            if i > 0 and role == "assistant":
                total_transitions += 1

            prev_message = msg

    conn.commit()
    conn.close()

    logger.info(
        f"Import complete: {total_messages} messages, {total_transitions} transitions"
    )
    return total_transitions


def main():
    parser = argparse.ArgumentParser(
        description="Import chat history for RL pre-training"
    )
    parser.add_argument(
        "--chat-history-dir",
        type=str,
        default="data/chat_history",
        help="Directory containing JSON chat history files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/conversations.db",
        help="Output SQLite database path",
    )
    parser.add_argument(
        "--min-quality",
        type=float,
        default=0.3,
        help="Minimum quality score (0.0-1.0)",
    )

    args = parser.parse_args()

    chat_history_dir = Path(args.chat_history_dir)
    output_db = Path(args.output)

    if not chat_history_dir.exists():
        logger.error(f"Chat history directory not found: {chat_history_dir}")
        return 1

    json_files = list(chat_history_dir.glob("*.json"))
    if not json_files:
        logger.error(f"No JSON files found in {chat_history_dir}")
        return 1

    logger.info(f"Found {len(json_files)} chat history files")
    logger.info(f"Output database: {output_db}")

    transitions = import_chat_history(
        chat_history_dir=chat_history_dir,
        output_db=output_db,
        min_quality=args.min_quality,
    )

    if transitions == 0:
        logger.warning("No transitions imported - check quality threshold")
        return 1

    logger.info("=" * 60)
    logger.info("Import successful!")
    logger.info("=" * 60)
    logger.info(f"You can now run offline RL training with:")
    logger.info(f"  python scripts/train_offline_rl.py --db-path {output_db}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
