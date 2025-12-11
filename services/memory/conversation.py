"""Multi-turn conversation manager for complex tasks."""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """States for multi-turn conversations."""
    ACTIVE = "active"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class ConversationStep:
    """A step in a multi-turn conversation."""
    prompt: str  # What to ask the user
    validator: Optional[Callable[[str], bool]] = None  # Validate user input
    error_message: str = "Invalid input. Please try again."
    max_attempts: int = 3
    timeout_seconds: int = 300  # 5 minutes default

    # Results
    attempts: int = 0
    user_response: Optional[str] = None
    is_valid: bool = False


@dataclass
class Conversation:
    """Represents a multi-turn conversation."""
    conversation_id: str
    user_id: int
    channel_id: int
    conversation_type: str  # Type of conversation (setup, guided_task, etc.)
    steps: List[ConversationStep]
    current_step_index: int = 0
    state: ConversationState = ConversationState.ACTIVE
    started_at: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)  # Store collected data

    def get_current_step(self) -> Optional[ConversationStep]:
        """Get the current step."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance_step(self) -> bool:
        """Move to the next step.

        Returns:
            True if advanced, False if no more steps
        """
        self.current_step_index += 1
        if self.current_step_index >= len(self.steps):
            self.state = ConversationState.COMPLETED
            return False
        return True

    def is_active(self) -> bool:
        """Check if conversation is still active."""
        return self.state == ConversationState.ACTIVE or self.state == ConversationState.WAITING_FOR_INPUT

    def is_timed_out(self) -> bool:
        """Check if conversation has timed out."""
        current_step = self.get_current_step()
        if not current_step:
            return False

        elapsed = (datetime.now() - self.started_at).total_seconds()
        return elapsed > current_step.timeout_seconds


class MultiTurnConversationManager:
    """Manages multi-turn conversations for complex tasks."""

    def __init__(self):
        """Initialize the conversation manager."""
        self.active_conversations: Dict[int, Conversation] = {}  # channel_id -> conversation
        self.conversation_templates: Dict[str, List[ConversationStep]] = {}

        # Register default conversation templates
        self._register_default_templates()

        logger.info("Multi-turn conversation manager initialized")

    def _register_default_templates(self):
        """Register default conversation templates."""

        # Server setup wizard
        self.register_template(
            "server_setup",
            [
                ConversationStep(
                    prompt="Let's set up your server! First, what's your preferred prefix for commands? (e.g., !, ?, .)",
                    validator=lambda x: len(x) == 1 and not x.isalnum(),
                    error_message="Prefix should be a single special character (not a letter or number)."
                ),
                ConversationStep(
                    prompt="Great! Now, which channel should I use for announcements? (mention the channel or say 'skip')",
                    validator=lambda x: x.startswith('<#') or x.lower() == 'skip',
                    error_message="Please mention a channel or say 'skip'."
                ),
                ConversationStep(
                    prompt="Should I enable auto-replies in conversation? (yes/no)",
                    validator=lambda x: x.lower() in ['yes', 'no', 'y', 'n'],
                    error_message="Please answer 'yes' or 'no'."
                ),
            ]
        )

        # Persona creation wizard
        self.register_template(
            "create_persona",
            [
                ConversationStep(
                    prompt="Let's create a new persona! What should we call it? (lowercase, no spaces)",
                    validator=lambda x: x.islower() and '_' in x or x.isalnum(),
                    error_message="Use lowercase letters, numbers, and underscores only."
                ),
                ConversationStep(
                    prompt="What's a nice display name for this persona?",
                    validator=lambda x: len(x) > 0 and len(x) < 50,
                    error_message="Display name should be 1-50 characters."
                ),
                ConversationStep(
                    prompt="Give me a short description of this persona (1-2 sentences):",
                    validator=lambda x: len(x) > 10 and len(x) < 200,
                    error_message="Description should be 10-200 characters."
                ),
                ConversationStep(
                    prompt="Now the fun part! Write the system prompt that defines their personality:",
                    validator=lambda x: len(x) > 50,
                    error_message="System prompt should be at least 50 characters."
                ),
            ]
        )

        # Reminder series setup
        self.register_template(
            "reminder_series",
            [
                ConversationStep(
                    prompt="Let's set up a series of reminders! What's the task you want to be reminded about?",
                    validator=lambda x: len(x) > 0,
                    error_message="Please tell me what to remind you about."
                ),
                ConversationStep(
                    prompt="How often should I remind you? (daily, weekly, hourly)",
                    validator=lambda x: x.lower() in ['daily', 'weekly', 'hourly'],
                    error_message="Please choose: daily, weekly, or hourly"
                ),
                ConversationStep(
                    prompt="How many times should I send this reminder? (1-50)",
                    validator=lambda x: x.isdigit() and 1 <= int(x) <= 50,
                    error_message="Enter a number between 1 and 50."
                ),
            ]
        )

    def register_template(self, conversation_type: str, steps: List[ConversationStep]):
        """Register a conversation template.

        Args:
            conversation_type: Type identifier
            steps: List of conversation steps
        """
        self.conversation_templates[conversation_type] = steps
        logger.info(f"Registered conversation template: {conversation_type}")

    async def start_conversation(
        self,
        user_id: int,
        channel_id: int,
        conversation_type: str
    ) -> Optional[Conversation]:
        """Start a new multi-turn conversation.

        Args:
            user_id: User ID
            channel_id: Channel ID
            conversation_type: Type of conversation

        Returns:
            Conversation object or None if template not found
        """
        if conversation_type not in self.conversation_templates:
            logger.error(f"Unknown conversation type: {conversation_type}")
            return None

        # Check if there's already an active conversation in this channel
        if channel_id in self.active_conversations:
            logger.warning(f"Channel {channel_id} already has an active conversation")
            return None

        # Create conversation from template
        import uuid
        conversation_id = str(uuid.uuid4())[:8]

        # Deep copy the steps
        import copy
        steps = copy.deepcopy(self.conversation_templates[conversation_type])

        conversation = Conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            channel_id=channel_id,
            conversation_type=conversation_type,
            steps=steps
        )

        self.active_conversations[channel_id] = conversation
        logger.info(f"Started {conversation_type} conversation {conversation_id} in channel {channel_id}")

        return conversation

    async def process_response(
        self,
        channel_id: int,
        user_id: int,
        message: str
    ) -> Optional[Dict[str, Any]]:
        """Process a user response in an active conversation.

        Args:
            channel_id: Channel ID
            user_id: User ID
            message: User's message

        Returns:
            Dict with response info or None
        """
        conversation = self.active_conversations.get(channel_id)

        if not conversation:
            return None

        # Check if this user owns the conversation
        if conversation.user_id != user_id:
            return {
                'type': 'error',
                'message': "This conversation belongs to someone else. Please wait for them to finish."
            }

        # Check for cancellation
        if message.lower() in ['cancel', 'quit', 'exit', 'stop']:
            conversation.state = ConversationState.CANCELLED
            del self.active_conversations[channel_id]
            return {
                'type': 'cancelled',
                'message': "Conversation cancelled. No problem!"
            }

        # Get current step
        current_step = conversation.get_current_step()
        if not current_step:
            return None

        # Validate response
        current_step.attempts += 1

        is_valid = True
        if current_step.validator:
            is_valid = current_step.validator(message)

        if not is_valid:
            # Check max attempts
            if current_step.attempts >= current_step.max_attempts:
                conversation.state = ConversationState.CANCELLED
                del self.active_conversations[channel_id]
                return {
                    'type': 'failed',
                    'message': "Too many invalid attempts. Conversation cancelled. You can start over anytime!"
                }

            return {
                'type': 'invalid',
                'message': current_step.error_message,
                'attempts_remaining': current_step.max_attempts - current_step.attempts
            }

        # Valid response - store it
        current_step.user_response = message
        current_step.is_valid = True
        conversation.data[f'step_{conversation.current_step_index}'] = message

        # Advance to next step
        has_more = conversation.advance_step()

        if has_more:
            next_step = conversation.get_current_step()
            return {
                'type': 'next_step',
                'prompt': next_step.prompt,
                'step_number': conversation.current_step_index + 1,
                'total_steps': len(conversation.steps)
            }
        else:
            # Conversation completed
            completed_conversation = conversation
            del self.active_conversations[channel_id]
            return {
                'type': 'completed',
                'message': "All done! ✅",
                'conversation': completed_conversation
            }

    def get_conversation(self, channel_id: int) -> Optional[Conversation]:
        """Get active conversation for a channel.

        Args:
            channel_id: Channel ID

        Returns:
            Conversation or None
        """
        return self.active_conversations.get(channel_id)

    def cancel_conversation(self, channel_id: int) -> bool:
        """Cancel an active conversation.

        Args:
            channel_id: Channel ID

        Returns:
            True if cancelled, False if no active conversation
        """
        if channel_id in self.active_conversations:
            self.active_conversations[channel_id].state = ConversationState.CANCELLED
            del self.active_conversations[channel_id]
            logger.info(f"Cancelled conversation in channel {channel_id}")
            return True
        return False

    async def cleanup_timed_out_conversations(self):
        """Clean up conversations that have timed out."""
        to_remove = []

        for channel_id, conversation in self.active_conversations.items():
            if conversation.is_timed_out():
                conversation.state = ConversationState.TIMED_OUT
                to_remove.append(channel_id)
                logger.info(f"Conversation {conversation.conversation_id} timed out")

        for channel_id in to_remove:
            del self.active_conversations[channel_id]

        return len(to_remove)

    def get_active_count(self) -> int:
        """Get number of active conversations.

        Returns:
            Number of active conversations
        """
        return len(self.active_conversations)

    def get_stats(self) -> Dict[str, Any]:
        """Get conversation manager statistics.

        Returns:
            Statistics dict
        """
        return {
            'active_conversations': len(self.active_conversations),
            'registered_templates': len(self.conversation_templates),
            'templates': list(self.conversation_templates.keys())
        }
