"""Add helpful default custom intents to the bot.

This script populates the custom intents system with useful examples
that can be customized per server or used globally.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.custom_intents import CustomIntentManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_default_intents():
    """Add helpful default custom intents."""
    manager = CustomIntentManager()

    default_intents = [
        {
            'intent_id': 'server_info',
            'name': 'Server Information',
            'patterns': [
                r'(?:what|tell me about)\s+(?:this\s+)?server',
                r'server\s+info(?:rmation)?',
                r'about\s+(?:this\s+)?(?:discord|server)',
            ],
            'response_template': "This is a Discord server! Check the channel list and pinned messages for more information.",
            'response_type': 'text',
            'metadata': {'category': 'info', 'global': True}
        },
        {
            'intent_id': 'server_rules',
            'name': 'Server Rules',
            'patterns': [
                r'what\s+(?:are\s+)?(?:the\s+)?rules',
                r'show\s+(?:me\s+)?(?:the\s+)?rules',
                r'server\s+rules',
                r'can\s+i\s+(?:see|view)\s+(?:the\s+)?rules',
            ],
            'response_template': "Please check the rules channel for server guidelines, or ask a moderator!",
            'response_type': 'text',
            'metadata': {'category': 'info', 'global': True}
        },
        {
            'intent_id': 'get_help',
            'name': 'Get Help',
            'patterns': [
                r'(?:i\s+)?need\s+help',
                r'can\s+(?:someone|anyone)\s+help\s+me',
                r'help\s+(?:me|please)',
                r'someone\s+help',
            ],
            'response_template': "I see you need help! Try asking your question directly, or mention @Moderator if it's urgent.",
            'response_type': 'text',
            'metadata': {'category': 'support', 'global': True}
        },
        {
            'intent_id': 'report_issue',
            'name': 'Report Issue',
            'patterns': [
                r'report\s+(?:a\s+)?(?:bug|issue|problem)',
                r'found\s+(?:a\s+)?bug',
                r'something\s+(?:is\s+)?(?:broken|wrong)',
                r'(?:this\s+)?(?:isn\'?t|is\s+not)\s+working',
            ],
            'response_template': "Thanks for reporting! Please provide details about the issue and a moderator will look into it.",
            'response_type': 'text',
            'metadata': {'category': 'support', 'global': True}
        },
        {
            'intent_id': 'introduce_yourself',
            'name': 'Introduce Yourself',
            'patterns': [
                r'(?:i\'?m|i\s+am)\s+new\s+here',
                r'just\s+joined',
                r'new\s+(?:member|user|person)',
                r'where\s+(?:do\s+i|should\s+i)\s+introduce\s+myself',
            ],
            'response_template': "Welcome to the server! Feel free to introduce yourself in the appropriate channel. We're glad to have you!",
            'response_type': 'text',
            'metadata': {'category': 'welcome', 'global': True}
        },
        {
            'intent_id': 'moderator_contact',
            'name': 'Contact Moderator',
            'patterns': [
                r'(?:how\s+(?:do\s+i|can\s+i))\s+(?:contact|reach|talk\s+to)\s+(?:a\s+)?(?:mod|moderator|admin)',
                r'(?:where|who)\s+(?:are|is)\s+(?:the\s+)?(?:mods|moderators|admins)',
                r'i\s+need\s+(?:a\s+)?(?:mod|moderator|admin)',
            ],
            'response_template': "You can mention @Moderator or send a direct message to any moderator. Their names are highlighted in the member list!",
            'response_type': 'text',
            'metadata': {'category': 'info', 'global': True}
        },
        {
            'intent_id': 'bot_commands',
            'name': 'Bot Commands',
            'patterns': [
                r'(?:what|which)\s+commands\s+(?:does\s+)?(?:the\s+)?(?:bot|you)\s+have',
                r'(?:bot|your)\s+commands',
                r'what\s+can\s+(?:the\s+)?(?:bot|you)\s+do',
                r'(?:list|show)\s+(?:all\s+)?commands',
            ],
            'response_template': "Type `/` to see all available slash commands! Try /help for more information.",
            'response_type': 'text',
            'metadata': {'category': 'bot', 'global': True}
        },
        {
            'intent_id': 'current_activity',
            'name': 'Current Activity',
            'patterns': [
                r'what\'?s\s+(?:going\s+on|happening)',
                r'what\s+(?:are\s+(?:people|we|you))\s+(?:talking\s+about|doing)',
                r'(?:any|what)\s+(?:events|activities)',
                r'what\'?s\s+the\s+(?:topic|vibe)',
            ],
            'response_template': "Check the recent messages in active channels to see what's happening! Join in wherever you'd like.",
            'response_type': 'text',
            'metadata': {'category': 'info', 'global': True}
        },
    ]

    # Add all default intents as global
    added = 0
    skipped = 0

    for intent_data in default_intents:
        success = manager.add_intent(
            server_id=None,  # Global
            intent_id=intent_data['intent_id'],
            name=intent_data['name'],
            patterns=intent_data['patterns'],
            response_template=intent_data.get('response_template'),
            response_type=intent_data.get('response_type', 'text'),
            metadata=intent_data.get('metadata', {})
        )

        if success:
            added += 1
            logger.info(f"✅ Added global intent: {intent_data['name']}")
        else:
            skipped += 1
            logger.warning(f"⚠️ Skipped (already exists): {intent_data['name']}")

    logger.info(f"\n📊 Summary: Added {added} intents, skipped {skipped} existing intents")
    logger.info(f"Total global intents: {len(manager.global_intents)}")

    return manager


if __name__ == "__main__":
    print("🎯 Adding Default Custom Intents\n")
    manager = add_default_intents()
    print("\n✨ Done! Restart the bot to use these intents.")
    print("\n💡 Tip: Use /add_intent to add server-specific intents")
    print("📋 Use /list_intents to see all available intents")
