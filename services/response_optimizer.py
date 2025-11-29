"""Response optimization service for dynamic token limits and query analysis."""
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class ResponseOptimizer:
    """Analyzes queries and optimizes response parameters for better performance."""

    # Query patterns for classification
    PATTERNS = {
        'greeting': [
            r'\b(hi|hello|hey|sup|yo|greetings)\b',
            r'\b(good morning|good afternoon|good evening)\b',
            r'\b(howdy|what\'?s up)\b',
        ],
        'acknowledgment': [
            r'\b(ok|okay|cool|nice|thanks|thank you|thx|ty)\b',
            r'\b(got it|understood|alright|sounds good)\b',
            r'\b(yes|no|yeah|nah|yep|nope)\b',
        ],
        'simple_question': [
            r'\b(what|who|when|where|which|why|how)\s+\w+\?',
            r'\b(is|are|can|could|would|will|should)\s+\w+\?',
            r'\b(do|does|did|has|have)\s+\w+\?',
        ],
        'complex_question': [
            r'\b(explain|describe|tell me about|what do you think)\b',
            r'\b(how does.*work|why does.*happen|what causes)\b',
            r'\b(can you.*explain|could you.*describe)\b',
        ],
        'creative_request': [
            r'\b(write|create|make|generate|compose)\b',
            r'\b(story|poem|song|joke|list)\b',
            r'\b(imagine|pretend|what if)\b',
        ],
        'command': [
            r'\b(search|find|look up|show me)\b',
            r'\b(remind|set reminder|schedule)\b',
            r'\b(play|stop|pause|skip|join|leave)\b',
        ],
    }

    @classmethod
    def classify_query(cls, text: str) -> str:
        """Classify query type based on content.

        Args:
            text: User query text

        Returns:
            Query classification: greeting, acknowledgment, simple_question,
            complex_question, creative_request, command, or conversational
        """
        text_lower = text.lower()

        # Check each pattern category
        for category, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return category

        # Default to conversational
        return 'conversational'

    @classmethod
    def estimate_optimal_tokens(
        cls,
        query: str,
        query_type: Optional[str] = None,
        default_max_tokens: int = 500
    ) -> Tuple[int, str]:
        """Estimate optimal max_tokens for a query.

        Args:
            query: User query text
            query_type: Optional pre-classified query type
            default_max_tokens: Default max tokens if dynamic adjustment disabled

        Returns:
            Tuple of (max_tokens, reasoning)
        """
        if query_type is None:
            query_type = cls.classify_query(query)

        # Token allocation by query type
        token_map = {
            'greeting': (75, 'Short greeting response'),
            'acknowledgment': (50, 'Minimal acknowledgment'),
            'simple_question': (200, 'Concise answer to simple question'),
            'complex_question': (400, 'Detailed explanation'),
            'creative_request': (800, 'Creative content generation'),
            'command': (150, 'Command execution with brief confirmation'),
            'conversational': (300, 'Standard conversational response'),
        }

        max_tokens, reasoning = token_map.get(
            query_type,
            (default_max_tokens, 'Default allocation')
        )

        # Adjust based on query length
        word_count = len(query.split())

        if word_count > 50:
            # Long query likely needs detailed response
            max_tokens = min(max_tokens + 200, 1000)
            reasoning += ' (increased for long query)'
        elif word_count < 5:
            # Very short query likely needs short response
            max_tokens = min(max_tokens, 150)
            reasoning += ' (reduced for short query)'

        # Check for explicit detail requests
        detail_keywords = [
            'explain in detail', 'tell me everything', 'comprehensive',
            'thoroughly', 'elaborate', 'in depth', 'detailed'
        ]
        if any(keyword in query.lower() for keyword in detail_keywords):
            max_tokens = min(max_tokens + 300, 1000)
            reasoning += ' (increased for explicit detail request)'

        logger.debug(
            f"Query type: {query_type} | "
            f"Optimal tokens: {max_tokens} | "
            f"Reasoning: {reasoning}"
        )

        return max_tokens, reasoning

    @classmethod
    def should_use_streaming(
        cls,
        query: str,
        estimated_tokens: Optional[int] = None,
        streaming_threshold: int = 300
    ) -> bool:
        """Determine if streaming should be used for this query.

        Args:
            query: User query text
            estimated_tokens: Pre-estimated optimal tokens
            streaming_threshold: Token threshold for streaming

        Returns:
            True if streaming should be used, False otherwise
        """
        if estimated_tokens is None:
            estimated_tokens, _ = cls.estimate_optimal_tokens(query)

        use_streaming = estimated_tokens >= streaming_threshold

        logger.debug(
            f"Streaming decision: {'enabled' if use_streaming else 'disabled'} | "
            f"Estimated tokens: {estimated_tokens} | "
            f"Threshold: {streaming_threshold}"
        )

        return use_streaming

    @classmethod
    def optimize_request_params(
        cls,
        query: str,
        base_params: dict,
        enable_dynamic_tokens: bool = True,
        streaming_threshold: int = 300
    ) -> dict:
        """Optimize LLM request parameters based on query.

        Args:
            query: User query text
            base_params: Base LLM parameters
            enable_dynamic_tokens: Enable dynamic token adjustment
            streaming_threshold: Token threshold for streaming

        Returns:
            Optimized parameters dict
        """
        params = base_params.copy()

        if enable_dynamic_tokens:
            # Classify query
            query_type = cls.classify_query(query)

            # Estimate optimal tokens
            optimal_tokens, reasoning = cls.estimate_optimal_tokens(
                query,
                query_type=query_type,
                default_max_tokens=base_params.get('max_tokens', 500)
            )

            # Update max_tokens
            params['max_tokens'] = optimal_tokens

            # Determine streaming
            use_streaming = cls.should_use_streaming(
                query,
                estimated_tokens=optimal_tokens,
                streaming_threshold=streaming_threshold
            )

            params['_optimization_info'] = {
                'query_type': query_type,
                'optimal_tokens': optimal_tokens,
                'reasoning': reasoning,
                'use_streaming': use_streaming,
            }

            logger.info(
                f"🎯 Response optimization: {query_type} → "
                f"{optimal_tokens} tokens | "
                f"Streaming: {'on' if use_streaming else 'off'}"
            )

        return params

    @classmethod
    def analyze_query_complexity(cls, query: str) -> dict:
        """Analyze query complexity for metrics/logging.

        Args:
            query: User query text

        Returns:
            Dict with complexity metrics
        """
        query_type = cls.classify_query(query)
        word_count = len(query.split())
        char_count = len(query)
        has_questions = '?' in query
        question_count = query.count('?')

        # Complexity score (0-10)
        complexity = 5  # Base

        if query_type in ['creative_request', 'complex_question']:
            complexity += 2
        elif query_type in ['greeting', 'acknowledgment']:
            complexity -= 3

        if word_count > 50:
            complexity += 1
        elif word_count < 5:
            complexity -= 1

        if question_count > 1:
            complexity += 1

        complexity = max(0, min(10, complexity))

        return {
            'query_type': query_type,
            'word_count': word_count,
            'char_count': char_count,
            'has_questions': has_questions,
            'question_count': question_count,
            'complexity_score': complexity,
        }
