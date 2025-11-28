"""Per-server custom intent definitions."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import re

logger = logging.getLogger(__name__)


class CustomIntent:
    """Represents a custom user-defined intent."""

    def __init__(
        self,
        intent_id: str,
        name: str,
        patterns: List[str],
        response_template: Optional[str] = None,
        response_type: str = "text",  # text, embed, command
        metadata: Optional[Dict] = None
    ):
        """Initialize custom intent.

        Args:
            intent_id: Unique identifier
            name: Display name
            patterns: List of regex patterns to match
            response_template: Optional response template
            response_type: Type of response
            metadata: Additional metadata
        """
        self.intent_id = intent_id
        self.name = name
        self.patterns = patterns
        self.response_template = response_template
        self.response_type = response_type
        self.metadata = metadata or {}
        self.usage_count = 0

    def matches(self, message: str) -> Optional[Dict[str, Any]]:
        """Check if message matches this intent.

        Args:
            message: User message

        Returns:
            Match data with groups or None
        """
        message_lower = message.lower().strip()

        for pattern in self.patterns:
            try:
                match = re.search(pattern, message_lower, re.IGNORECASE)
                if match:
                    self.usage_count += 1
                    return {
                        'intent_id': self.intent_id,
                        'name': self.name,
                        'pattern': pattern,
                        'groups': match.groups(),
                        'response_template': self.response_template,
                        'response_type': self.response_type,
                        'metadata': self.metadata
                    }
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern}': {e}")
                continue

        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary.

        Returns:
            Dict representation
        """
        return {
            'intent_id': self.intent_id,
            'name': self.name,
            'patterns': self.patterns,
            'response_template': self.response_template,
            'response_type': self.response_type,
            'metadata': self.metadata,
            'usage_count': self.usage_count
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CustomIntent':
        """Create from dictionary.

        Args:
            data: Dict representation

        Returns:
            CustomIntent instance
        """
        intent = cls(
            intent_id=data['intent_id'],
            name=data['name'],
            patterns=data['patterns'],
            response_template=data.get('response_template'),
            response_type=data.get('response_type', 'text'),
            metadata=data.get('metadata', {})
        )
        intent.usage_count = data.get('usage_count', 0)
        return intent


class CustomIntentManager:
    """Manages per-server custom intents."""

    def __init__(self, data_dir: Path = None):
        """Initialize the custom intent manager.

        Args:
            data_dir: Directory to store custom intents
        """
        from config import Config
        self.data_dir = data_dir or (Config.DATA_DIR / "custom_intents")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Server intents: server_id -> {intent_id -> CustomIntent}
        self.server_intents: Dict[int, Dict[str, CustomIntent]] = {}

        # Global intents (apply to all servers)
        self.global_intents: Dict[str, CustomIntent] = {}

        # Load existing intents
        self._load_all_intents()

        logger.info("Custom intent manager initialized")

    def _load_all_intents(self):
        """Load all custom intents from disk."""
        # Load global intents
        global_file = self.data_dir / "global_intents.json"
        if global_file.exists():
            try:
                with open(global_file, 'r') as f:
                    data = json.load(f)
                    for intent_data in data:
                        intent = CustomIntent.from_dict(intent_data)
                        self.global_intents[intent.intent_id] = intent
                logger.info(f"Loaded {len(self.global_intents)} global custom intents")
            except Exception as e:
                logger.error(f"Failed to load global intents: {e}")

        # Load server-specific intents
        for server_file in self.data_dir.glob("server_*.json"):
            try:
                server_id = int(server_file.stem.replace("server_", ""))
                with open(server_file, 'r') as f:
                    data = json.load(f)
                    self.server_intents[server_id] = {}
                    for intent_data in data:
                        intent = CustomIntent.from_dict(intent_data)
                        self.server_intents[server_id][intent.intent_id] = intent
                logger.info(f"Loaded {len(self.server_intents[server_id])} intents for server {server_id}")
            except Exception as e:
                logger.error(f"Failed to load intents from {server_file}: {e}")

    def _save_server_intents(self, server_id: int):
        """Save intents for a specific server.

        Args:
            server_id: Server ID
        """
        if server_id not in self.server_intents:
            return

        server_file = self.data_dir / f"server_{server_id}.json"
        try:
            intents_data = [
                intent.to_dict()
                for intent in self.server_intents[server_id].values()
            ]
            with open(server_file, 'w') as f:
                json.dump(intents_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save server {server_id} intents: {e}")

    def _save_global_intents(self):
        """Save global intents."""
        global_file = self.data_dir / "global_intents.json"
        try:
            intents_data = [
                intent.to_dict()
                for intent in self.global_intents.values()
            ]
            with open(global_file, 'w') as f:
                json.dump(intents_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save global intents: {e}")

    def add_intent(
        self,
        server_id: Optional[int],
        intent_id: str,
        name: str,
        patterns: List[str],
        response_template: Optional[str] = None,
        response_type: str = "text",
        metadata: Optional[Dict] = None
    ) -> bool:
        """Add a custom intent.

        Args:
            server_id: Server ID or None for global
            intent_id: Unique identifier
            name: Display name
            patterns: List of regex patterns
            response_template: Optional response template
            response_type: Type of response
            metadata: Additional metadata

        Returns:
            True if added successfully
        """
        intent = CustomIntent(
            intent_id=intent_id,
            name=name,
            patterns=patterns,
            response_template=response_template,
            response_type=response_type,
            metadata=metadata
        )

        if server_id is None:
            # Global intent
            if intent_id in self.global_intents:
                logger.warning(f"Global intent {intent_id} already exists")
                return False
            self.global_intents[intent_id] = intent
            self._save_global_intents()
        else:
            # Server-specific intent
            if server_id not in self.server_intents:
                self.server_intents[server_id] = {}

            if intent_id in self.server_intents[server_id]:
                logger.warning(f"Intent {intent_id} already exists for server {server_id}")
                return False

            self.server_intents[server_id][intent_id] = intent
            self._save_server_intents(server_id)

        logger.info(f"Added custom intent {intent_id} for {'global' if server_id is None else f'server {server_id}'}")
        return True

    def remove_intent(self, server_id: Optional[int], intent_id: str) -> bool:
        """Remove a custom intent.

        Args:
            server_id: Server ID or None for global
            intent_id: Intent ID

        Returns:
            True if removed
        """
        if server_id is None:
            if intent_id in self.global_intents:
                del self.global_intents[intent_id]
                self._save_global_intents()
                return True
        else:
            if server_id in self.server_intents and intent_id in self.server_intents[server_id]:
                del self.server_intents[server_id][intent_id]
                self._save_server_intents(server_id)
                return True

        return False

    def check_custom_intent(self, server_id: Optional[int], message: str) -> Optional[Dict[str, Any]]:
        """Check if message matches any custom intent.

        Args:
            server_id: Server ID or None
            message: User message

        Returns:
            Match data or None
        """
        # Check global intents first
        for intent in self.global_intents.values():
            match = intent.matches(message)
            if match:
                return match

        # Check server-specific intents
        if server_id and server_id in self.server_intents:
            for intent in self.server_intents[server_id].values():
                match = intent.matches(message)
                if match:
                    return match

        return None

    def list_intents(self, server_id: Optional[int] = None) -> List[Dict]:
        """List all intents for a server.

        Args:
            server_id: Server ID or None for all

        Returns:
            List of intent dicts
        """
        intents = []

        # Add global intents
        intents.extend([intent.to_dict() for intent in self.global_intents.values()])

        # Add server-specific intents
        if server_id and server_id in self.server_intents:
            intents.extend([intent.to_dict() for intent in self.server_intents[server_id].values()])

        return intents

    def get_stats(self, server_id: Optional[int] = None) -> Dict:
        """Get statistics.

        Args:
            server_id: Server ID or None for global

        Returns:
            Statistics dict
        """
        if server_id is None:
            return {
                'global_intents': len(self.global_intents),
                'total_servers': len(self.server_intents),
                'total_intents': len(self.global_intents) + sum(
                    len(intents) for intents in self.server_intents.values()
                )
            }
        else:
            server_count = len(self.server_intents.get(server_id, {}))
            return {
                'server_id': server_id,
                'custom_intents': server_count,
                'global_intents': len(self.global_intents),
                'total_available': server_count + len(self.global_intents)
            }


# Example custom intents that could be added

EXAMPLE_CUSTOM_INTENTS = [
    {
        'intent_id': 'server_rules',
        'name': 'Server Rules',
        'patterns': [
            r'what\s+(?:are\s+)?(?:the\s+)?rules',
            r'show\s+(?:me\s+)?(?:the\s+)?rules',
            r'server\s+rules',
        ],
        'response_template': "Here are our server rules:\n1. Be respectful\n2. No spamming\n3. Have fun!",
        'response_type': 'text'
    },
    {
        'intent_id': 'support_ticket',
        'name': 'Support Ticket',
        'patterns': [
            r'(?:open|create|make)\s+(?:a\s+)?(?:support\s+)?ticket',
            r'i\s+need\s+help\s+(?:with|from)',
            r'support\s+request',
        ],
        'response_template': "I'll help you create a support ticket! Please use `/ticket` or DM a moderator.",
        'response_type': 'text',
        'metadata': {'category': 'support'}
    },
    {
        'intent_id': 'apply',
        'name': 'Application',
        'patterns': [
            r'how\s+(?:do\s+i|can\s+i)\s+apply',
            r'application\s+process',
            r'(?:where|how)\s+(?:to|do\s+i)\s+submit\s+(?:an\s+)?application',
        ],
        'response_template': "To apply, please visit #applications and fill out the form!",
        'response_type': 'text',
        'metadata': {'category': 'info'}
    }
]
