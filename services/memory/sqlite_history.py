"""SQLite-backed chat history manager (drop-in replacement for JSON-based system)."""

import sqlite3
import json
import logging
import aiosqlite
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SQLiteChatHistory:
    """SQLite-based chat history storage with same interface as ChatHistoryManager."""

    def __init__(self, db_path: Path):
        """
        Initialize SQLite chat history.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database synchronously
        self._init_db()
        
        logger.info(f"SQLite chat history initialized at {db_path}")

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    username TEXT,
                    user_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_channel (channel_id),
                    INDEX idx_timestamp (timestamp)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    channel_id INTEGER PRIMARY KEY,
                    summary TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()

    async def load_history(
        self, channel_id: int, max_messages: int = 100
    ) -> List[Dict[str, str]]:
        """
        Load chat history for a channel.
        
        Args:
            channel_id: Discord channel ID
            max_messages: Maximum messages to return
            
        Returns:
            List of message dicts
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT role, content, username, user_id 
                FROM messages 
                WHERE channel_id = ? 
                ORDER BY id DESC 
                LIMIT ?
                """,
                (channel_id, max_messages)
            ) as cursor:
                rows = await cursor.fetchall()
                
                # Reverse to get chronological order
                messages = []
                for row in reversed(rows):
                    msg = {
                        "role": row[0],
                        "content": row[1],
                    }
                    if row[2]:  # username
                        msg["username"] = row[2]
                    if row[3]:  # user_id
                        msg["user_id"] = row[3]
                    messages.append(msg)
                
                return messages

    async def add_message(
        self,
        channel_id: int,
        role: str,
        content: str,
        username: Optional[str] = None,
        user_id: Optional[int] = None
    ):
        """
        Add a message to history.
        
        Args:
            channel_id: Discord channel ID
            role: Message role ('user' or 'assistant')
            content: Message content
            username: Optional username
            user_id: Optional user ID
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (channel_id, role, content, username, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (channel_id, role, content, username, user_id)
            )
            await db.commit()

    async def save_summary(self, channel_id: int, summary: str):
        """
        Save or update a summary for a channel.
        
        Args:
            channel_id: Discord channel ID
            summary: Summary text
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO summaries (channel_id, summary)
                VALUES (?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET summary=?, updated_at=CURRENT_TIMESTAMP
                """,
                (channel_id, summary, summary)
            )
            await db.commit()

    async def get_summary(self, channel_id: int) -> Optional[str]:
        """
        Get summary for a channel.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            Summary text or None
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT summary FROM summaries WHERE channel_id = ?",
                (channel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def clear_history(self, channel_id: int):
        """
        Clear history for a channel.
        
        Args:
            channel_id: Discord channel ID
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM messages WHERE channel_id = ?",
                (channel_id,)
            )
            await db.execute(
                "DELETE FROM summaries WHERE channel_id = ?",
                (channel_id,)
            )
            await db.commit()

    def get_conversation_participants(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict]:
        """
        Get unique participants from messages.
        
        Args:
            messages: List of message dicts
            
        Returns:
            List of participant info dicts
        """
        participants = {}
        for msg in messages:
            if msg.get("user_id") and msg.get("user_id") not in participants:
                participants[msg["user_id"]] = {
                    "user_id": msg["user_id"],
                    "username": msg.get("username", "Unknown")
                }
        return list(participants.values())

    async def migrate_from_json(self, json_dir: Path):
        """
        Migrate existing JSON history files to SQLite.
        
        Args:
            json_dir: Directory containing JSON history files
        """
        logger.info(f"Migrating chat history from {json_dir}")
        migrated = 0
        
        for json_file in json_dir.glob("*.json"):
            channel_id = int(json_file.stem)
            
            try:
                with open(json_file, 'r') as f:
                    messages = json.load(f)
                
                async with aiosqlite.connect(self.db_path) as db:
                    for msg in messages:
                        await db.execute(
                            """
                            INSERT INTO messages (channel_id, role, content, username, user_id)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                channel_id,
                                msg.get("role"),
                                msg.get("content"),
                                msg.get("username"),
                                msg.get("user_id")
                            )
                        )
                    await db.commit()
                
                migrated += 1
                logger.info(f"Migrated {len(messages)} messages from channel {channel_id}")
            
            except Exception as e:
                logger.error(f"Failed to migrate {json_file}: {e}")
        
        logger.info(f"Migration complete: {migrated} channels")
