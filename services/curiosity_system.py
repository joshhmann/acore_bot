"""Curiosity System - bot asks natural follow-up questions."""
import logging
import random
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CuriosityOpportunity:
    """Represents an opportunity to ask a follow-up question."""
    topic: str
    context: str
    question_type: str  # "clarification", "deeper", "related", "update"
    confidence: float  # 0.0 to 1.0
    timestamp: datetime


class CuriositySystem:
    """Manages natural follow-up questions and curiosity."""

    def __init__(self, ollama_service):
        """Initialize curiosity system.

        Args:
            ollama_service: Ollama service for generating questions
        """
        self.ollama = ollama_service
        self.compiled_persona = None  # Set by main.py or character_commands

        # Track what we've asked about recently
        self.recent_questions: Dict[int, List[str]] = defaultdict(list)  # channel_id -> questions
        self.question_cooldown = timedelta(minutes=15)  # Don't ask too frequently
        self.last_question_time: Dict[int, datetime] = {}  # channel_id -> timestamp

        # Curiosity triggers
        self.curiosity_keywords = [
            "working on", "planning", "building", "creating", "thinking about",
            "trying to", "going to", "want to", "hope to", "excited about",
            "problem", "issue", "challenge", "difficult", "struggling",
            "new", "recently", "just", "started", "finished",
        ]

        logger.info("Curiosity system initialized")

    def set_persona(self, compiled_persona):
        """Update the current persona.

        Args:
            compiled_persona: Compiled persona (character + framework)
        """
        self.compiled_persona = compiled_persona
        logger.debug(f"Curiosity system updated with persona: {compiled_persona.persona_id if compiled_persona else 'None'}")

    async def should_ask_question(
        self,
        message_content: str,
        channel_id: int,
        conversation_context: Optional[List[str]] = None
    ) -> Optional[CuriosityOpportunity]:
        """Determine if bot should ask a follow-up question.

        Args:
            message_content: User's message
            channel_id: Discord channel ID
            conversation_context: Recent conversation messages

        Returns:
            CuriosityOpportunity if should ask, None otherwise
        """
        try:
            # Check cooldown
            if channel_id in self.last_question_time:
                time_since_last = datetime.now() - self.last_question_time[channel_id]
                if time_since_last < self.question_cooldown:
                    return None

            # Check for curiosity triggers
            message_lower = message_content.lower()
            has_trigger = any(keyword in message_lower for keyword in self.curiosity_keywords)

            if not has_trigger:
                # Occasional random curiosity (5% chance)
                if random.random() > 0.05:
                    return None

            # Build context
            context = "\n".join(conversation_context[-3:]) if conversation_context else ""

            # Ask LLM to assess curiosity opportunity
            prompt = f"""Analyze this message and determine if there's an opportunity to ask a natural follow-up question.

Message: {message_content}

Recent context:
{context}

Assess:
1. Is there something interesting to ask about? (yes/no)
2. What's the topic?
3. Question type: clarification / deeper / related / update
4. Confidence (0.0 to 1.0, where 0.7+ means ask)

Respond in format:
interesting: yes/no
topic: [topic]
type: [question_type]
confidence: [0.0-1.0]

Response:"""

            response = await self.ollama.generate(prompt, max_tokens=150)

            if not response:
                return None

            # Parse response
            lines = response.strip().lower().split('\n')
            data = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    data[key.strip()] = value.strip()

            interesting = data.get('interesting', 'no')
            if interesting != 'yes':
                return None

            topic = data.get('topic', '')
            question_type = data.get('type', 'clarification')
            confidence = float(data.get('confidence', '0.0'))

            # Check if confident enough
            if confidence < 0.5 or not topic:
                return None

            # Check if we've asked about this recently
            recent_topics = self.recent_questions.get(channel_id, [])
            if topic.lower() in [t.lower() for t in recent_topics[-5:]]:
                return None

            return CuriosityOpportunity(
                topic=topic,
                context=context,
                question_type=question_type,
                confidence=confidence,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.warning(f"Failed to assess curiosity opportunity: {e}")
            return None

    async def generate_followup_question(
        self,
        opportunity: CuriosityOpportunity,
        message_content: str
    ) -> Optional[str]:
        """Generate a natural follow-up question.

        Args:
            opportunity: CuriosityOpportunity from should_ask_question
            message_content: Original user message

        Returns:
            Follow-up question or None
        """
        try:
            # Use persona if available
            if self.compiled_persona:
                system_prompt = self.compiled_persona.system_prompt
                character_name = self.compiled_persona.character.display_name
            else:
                system_prompt = "You are a curious and friendly Discord bot."
                character_name = "Bot"

            # Question type guidance
            type_guidance = {
                "clarification": "Ask for clarification or more details about what they said.",
                "deeper": "Ask a deeper question that explores their reasoning or approach.",
                "related": "Ask about something related to the topic they mentioned.",
                "update": "Ask for an update on their progress or current status."
            }

            guidance = type_guidance.get(opportunity.question_type, type_guidance["clarification"])

            prompt = f"""{system_prompt}

User just said: "{message_content}"

Topic: {opportunity.topic}
Context: {opportunity.context}

Generate a natural, conversational follow-up question. {guidance}

The question should:
- Be in character
- Sound genuinely curious (not forced)
- Be 1 sentence only
- NOT sound like an interrogation
- Be specific to what they mentioned

Just the question, nothing else:"""

            response = await self.ollama.generate(prompt, max_tokens=100)

            if response and len(response.strip()) > 0:
                question = response.strip()

                # Clean up quotes
                if question.startswith('"') and question.endswith('"'):
                    question = question[1:-1]

                # Validate
                if 10 < len(question) < 200 and '?' in question:
                    return question

        except Exception as e:
            logger.error(f"Failed to generate follow-up question: {e}")

        return None

    def mark_question_asked(self, channel_id: int, topic: str):
        """Mark that a question was asked.

        Args:
            channel_id: Discord channel ID
            topic: Topic that was asked about
        """
        self.recent_questions[channel_id].append(topic)

        # Keep only last 10 topics per channel
        if len(self.recent_questions[channel_id]) > 10:
            self.recent_questions[channel_id] = self.recent_questions[channel_id][-10:]

        self.last_question_time[channel_id] = datetime.now()
        logger.debug(f"Marked curiosity question asked in channel {channel_id}: {topic}")

    def get_stats(self) -> Dict:
        """Get curiosity system statistics.

        Returns:
            Statistics dictionary
        """
        total_questions = sum(len(qs) for qs in self.recent_questions.values())

        return {
            "total_questions_asked": total_questions,
            "channels_tracked": len(self.recent_questions),
            "recent_questions_by_channel": {
                str(cid): topics[-3:] for cid, topics in self.recent_questions.items()
            },
            "config": {
                "cooldown_minutes": self.question_cooldown.total_seconds() / 60,
            }
        }
