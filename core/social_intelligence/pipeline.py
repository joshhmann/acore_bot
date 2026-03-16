"""Observation pipeline for the Social Intelligence Layer.

This module provides the ObservationPipeline class for capturing and analyzing
events to extract social signals and build social context.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

from core.social_intelligence.types import (
    SocialContext,
    SocialEvent,
    SocialSignal,
    VibeProfile,
    EngagementOpportunity,
    SignalType,
)

logger = logging.getLogger(__name__)


class SignalExtractor(ABC):
    """Abstract base class for signal extraction components.

    Signal extractors analyze events and extract specific types of
    social signals (sentiment, formality, urgency, etc.).
    """

    @property
    @abstractmethod
    def signal_type(self) -> SignalType:
        """The type of signal this extractor produces."""
        pass

    @abstractmethod
    async def extract(
        self, event: SocialEvent, context: Optional[SocialContext] = None
    ) -> Optional[SocialSignal]:
        """Extract a signal from the given event.

        Args:
            event: The social event to analyze.
            context: Optional existing social context.

        Returns:
            The extracted signal, or None if no signal detected.
        """
        pass


class VibeAnalyzer(ABC):
    """Abstract base class for vibe/atmosphere analysis.

    Vibe analyzers compute the overall emotional and social atmosphere
    from a collection of signals and context.
    """

    @abstractmethod
    async def analyze(
        self, signals: List[SocialSignal], context: Optional[SocialContext] = None
    ) -> VibeProfile:
        """Analyze signals to compute vibe profile.

        Args:
            signals: List of detected social signals.
            context: Optional existing social context.

        Returns:
            Computed vibe profile.
        """
        pass


class OpportunityDetector(ABC):
    """Abstract base class for engagement opportunity detection.

    Opportunity detectors identify moments where proactive engagement
    would be appropriate or valuable.
    """

    @abstractmethod
    async def detect(self, context: SocialContext) -> List[EngagementOpportunity]:
        """Detect engagement opportunities from social context.

        Args:
            context: The current social context.

        Returns:
            List of detected opportunities.
        """
        pass


class ObservationPipeline:
    """Pipeline for observing events and building social context.

    The pipeline coordinates signal extractors, vibe analyzers, and
    opportunity detectors to transform raw events into rich social context
    that can inform proactive behavior decisions.

    Attributes:
        signal_extractors: Registered signal extraction components.
        vibe_analyzer: Vibe analysis component (optional).
        opportunity_detectors: Registered opportunity detection components.
        max_signals_per_context: Maximum signals to retain in context.
    """

    def __init__(
        self,
        signal_extractors: Optional[List[SignalExtractor]] = None,
        vibe_analyzer: Optional[VibeAnalyzer] = None,
        opportunity_detectors: Optional[List[OpportunityDetector]] = None,
        max_signals_per_context: int = 10,
    ):
        """Initialize the observation pipeline.

        Args:
            signal_extractors: List of signal extractors to use.
            vibe_analyzer: Vibe analyzer to use.
            opportunity_detectors: List of opportunity detectors to use.
            max_signals_per_context: Maximum number of signals to retain.
        """
        self.signal_extractors = signal_extractors or []
        self.vibe_analyzer = vibe_analyzer
        self.opportunity_detectors = opportunity_detectors or []
        self.max_signals_per_context = max_signals_per_context

        self._signal_history: List[SocialSignal] = []
        self._max_history = 100

        logger.debug(
            f"ObservationPipeline initialized with {len(self.signal_extractors)} "
            f"extractors, {len(self.opportunity_detectors)} detectors"
        )

    def register_extractor(self, extractor: SignalExtractor) -> None:
        """Register a signal extractor.

        Args:
            extractor: The extractor to register.
        """
        self.signal_extractors.append(extractor)
        logger.debug(f"Registered signal extractor: {extractor.signal_type.value}")

    def register_opportunity_detector(self, detector: OpportunityDetector) -> None:
        """Register an opportunity detector.

        Args:
            detector: The detector to register.
        """
        self.opportunity_detectors.append(detector)
        logger.debug("Registered opportunity detector")

    def set_vibe_analyzer(self, analyzer: VibeAnalyzer) -> None:
        """Set the vibe analyzer.

        Args:
            analyzer: The vibe analyzer to use.
        """
        self.vibe_analyzer = analyzer
        logger.debug("Set vibe analyzer")

    async def process_event(
        self,
        event: SocialEvent,
        existing_context: Optional[SocialContext] = None,
    ) -> SocialContext:
        """Process an event through the pipeline to build social context.

        This is the main entry point for the pipeline. It extracts signals,
        analyzes vibe, detects opportunities, and returns a comprehensive
        social context.

        Args:
            event: The social event to process.
            existing_context: Optional existing context to build upon.

        Returns:
            Computed social context for the event.
        """
        logger.debug(f"Processing event {event.event_id} through observation pipeline")

        # Start with existing context or create new
        if existing_context:
            context = SocialContext(
                context_id=existing_context.context_id,
                timestamp=datetime.now(timezone.utc),
                vibe=existing_context.vibe,
                conversation=existing_context.conversation,
                relationship=existing_context.relationship,
                recent_signals=existing_context.recent_signals.copy(),
                user_patterns=existing_context.user_patterns.copy(),
                metadata=existing_context.metadata.copy(),
            )
        else:
            context = SocialContext()

        # Extract signals from event
        new_signals = await self._extract_signals(event, context)

        # Update signal history
        self._signal_history.extend(new_signals)
        if len(self._signal_history) > self._max_history:
            self._signal_history = self._signal_history[-self._max_history :]

        # Add new signals to context (maintaining max limit)
        context.recent_signals.extend(new_signals)
        if len(context.recent_signals) > self.max_signals_per_context:
            context.recent_signals = context.recent_signals[
                -self.max_signals_per_context :
            ]

        # Analyze vibe if analyzer available
        if self.vibe_analyzer:
            try:
                context.vibe = await self.vibe_analyzer.analyze(
                    context.recent_signals, context
                )
            except Exception as e:
                logger.warning(f"Vibe analysis failed: {e}")

        # Detect opportunities
        opportunities = await self._detect_opportunities(context)
        context.engagement_opportunities = opportunities

        # Attach context to event
        event.social_context = context

        logger.debug(
            f"Pipeline complete for event {event.event_id}: "
            f"{len(new_signals)} signals, {len(opportunities)} opportunities"
        )

        return context

    async def _extract_signals(
        self,
        event: SocialEvent,
        context: SocialContext,
    ) -> List[SocialSignal]:
        """Extract signals from event using registered extractors.

        Args:
            event: The event to analyze.
            context: Current social context.

        Returns:
            List of extracted signals.
        """
        signals: List[SocialSignal] = []

        for extractor in self.signal_extractors:
            try:
                signal = await extractor.extract(event, context)
                if signal:
                    signals.append(signal)
                    logger.debug(
                        f"Extracted {signal.signal_type.value} signal: {signal.value:.2f}"
                    )
            except Exception as e:
                logger.warning(
                    f"Signal extractor {extractor.signal_type.value} failed: {e}"
                )

        return signals

    async def _detect_opportunities(
        self, context: SocialContext
    ) -> List[EngagementOpportunity]:
        """Detect engagement opportunities using registered detectors.

        Args:
            context: Current social context.

        Returns:
            List of detected opportunities.
        """
        all_opportunities: List[EngagementOpportunity] = []

        for detector in self.opportunity_detectors:
            try:
                opportunities = await detector.detect(context)
                all_opportunities.extend(opportunities)
                logger.debug(f"Detector found {len(opportunities)} opportunities")
            except Exception as e:
                logger.warning(f"Opportunity detector failed: {e}")

        # Sort by priority (highest first)
        all_opportunities.sort(key=lambda o: o.priority, reverse=True)

        return all_opportunities

    def get_signal_history(
        self, signal_type: Optional[SignalType] = None
    ) -> List[SocialSignal]:
        """Get signal history, optionally filtered by type.

        Args:
            signal_type: Optional signal type to filter by.

        Returns:
            List of signals.
        """
        if signal_type:
            return [s for s in self._signal_history if s.signal_type == signal_type]
        return self._signal_history.copy()

    def clear_history(self) -> None:
        """Clear the signal history."""
        self._signal_history.clear()
        logger.debug("Signal history cleared")


class SimpleSentimentExtractor(SignalExtractor):
    """Simple rule-based sentiment extractor for scaffolding.

    This is a placeholder implementation that uses keyword-based
    sentiment detection. Production implementations should use
    proper NLP models.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SENTIMENT

    POSITIVE_WORDS = {
        "good",
        "great",
        "awesome",
        "excellent",
        "amazing",
        "love",
        "like",
        "happy",
        "excited",
        "wonderful",
        "fantastic",
        "best",
        "perfect",
        "thanks",
        "thank",
        "appreciate",
        "glad",
        "pleased",
        "lol",
        "haha",
    }

    NEGATIVE_WORDS = {
        "bad",
        "terrible",
        "awful",
        "hate",
        "dislike",
        "sad",
        "angry",
        "frustrated",
        "annoying",
        "worst",
        "horrible",
        "disappointed",
        "ugh",
        "ughh",
        "argh",
        "damn",
        "stupid",
        "dumb",
    }

    async def extract(
        self, event: SocialEvent, context: Optional[SocialContext] = None
    ) -> Optional[SocialSignal]:
        """Extract sentiment signal from event text."""
        if not event.raw_content:
            return None

        text = event.raw_content.lower()
        words = set(text.split())

        positive_count = len(words & self.POSITIVE_WORDS)
        negative_count = len(words & self.NEGATIVE_WORDS)

        if positive_count == 0 and negative_count == 0:
            return None

        # Calculate sentiment value (-1.0 to 1.0)
        total = positive_count + negative_count
        value = (positive_count - negative_count) / max(total, 1)

        # Confidence based on word count
        confidence = min(0.5 + (total * 0.1), 0.9)

        return SocialSignal(
            signal_type=SignalType.SENTIMENT,
            value=value,
            confidence=confidence,
            source="keyword_analysis",
        )


class SimpleVibeAnalyzer(VibeAnalyzer):
    """Simple rule-based vibe analyzer for scaffolding.

    Computes vibe profile from aggregated sentiment signals.
    """

    async def analyze(
        self, signals: List[SocialSignal], context: Optional[SocialContext] = None
    ) -> VibeProfile:
        """Analyze signals to compute vibe profile."""
        if not signals:
            return VibeProfile()

        # Aggregate sentiment signals
        sentiment_signals = [
            s for s in signals if s.signal_type == SignalType.SENTIMENT
        ]

        if not sentiment_signals:
            return VibeProfile()

        # Calculate weighted average sentiment
        total_weight = sum(s.confidence for s in sentiment_signals)
        avg_sentiment = (
            sum(s.value * s.confidence for s in sentiment_signals) / total_weight
        )

        # Map to PAD dimensions
        pleasure = avg_sentiment  # Sentiment maps to pleasure
        arousal = 0.0  # Would need more signals to determine

        # Confidence based on signal quality
        confidence = min(total_weight / len(sentiment_signals), 0.9)

        return VibeProfile(
            pleasure=pleasure,
            arousal=arousal,
            confidence=confidence,
        )


class SimpleOpportunityDetector(OpportunityDetector):
    """Simple opportunity detector for scaffolding.

    Detects basic engagement opportunities based on vibe and signals.
    """

    async def detect(self, context: SocialContext) -> List[EngagementOpportunity]:
        """Detect engagement opportunities."""
        opportunities: List[EngagementOpportunity] = []

        # Check for negative sentiment opportunity
        if context.vibe.pleasure < -0.5:
            opportunities.append(
                EngagementOpportunity(
                    opportunity_type="user_negative_sentiment",
                    priority=0.8,
                    confidence=context.vibe.confidence,
                    suggested_action="offer_support",
                    context="User showing negative sentiment",
                )
            )

        # Check for high engagement opportunity
        if context.vibe.engagement > 0.7:
            opportunities.append(
                EngagementOpportunity(
                    opportunity_type="high_engagement",
                    priority=0.6,
                    confidence=context.vibe.confidence,
                    suggested_action="maintain_momentum",
                    context="User highly engaged",
                )
            )

        return opportunities
