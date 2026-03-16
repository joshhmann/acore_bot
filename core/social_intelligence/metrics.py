"""Learning Evaluation Metrics.

Tracks and evaluates learning system performance:
- Engagement rates
- User satisfaction
- Mode switch accuracy
- Learning progress over time

Provides A/B testing capabilities and alerts for
performance degradation.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time."""

    timestamp: float
    engagement_rate: float
    user_satisfaction: float
    mode_accuracy: float
    avg_response_time: float
    total_interactions: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "engagement_rate": self.engagement_rate,
            "user_satisfaction": self.user_satisfaction,
            "mode_accuracy": self.mode_accuracy,
            "avg_response_time": self.avg_response_time,
            "total_interactions": self.total_interactions,
        }


class LearningMetricsTracker:
    """Tracks learning system performance metrics."""

    def __init__(self, history_size: int = 1000):
        self.history: deque[MetricSnapshot] = deque(maxlen=history_size)

        # Running counters
        self._total_engagements = 0
        self._successful_engagements = 0
        self._total_satisfaction_score = 0.0
        self._satisfaction_count = 0
        self._correct_mode_selections = 0
        self._total_mode_selections = 0
        self._response_times: deque[float] = deque(maxlen=100)

        # Alerts
        self._alert_thresholds = {
            "engagement_rate_min": 0.3,
            "satisfaction_min": 0.5,
            "degradation_window": 10,  # Number of snapshots to check
        }

    def record_engagement(self, success: bool) -> None:
        """Record an engagement attempt."""
        self._total_engagements += 1
        if success:
            self._successful_engagements += 1

    def record_satisfaction(self, score: float) -> None:
        """Record user satisfaction score (-1 to 1)."""
        self._total_satisfaction_score += score
        self._satisfaction_count += 1

    def record_mode_selection(self, correct: bool) -> None:
        """Record whether mode selection was correct."""
        self._total_mode_selections += 1
        if correct:
            self._correct_mode_selections += 1

    def record_response_time(self, seconds: float) -> None:
        """Record response time."""
        self._response_times.append(seconds)

    def capture_snapshot(self) -> MetricSnapshot:
        """Capture current metrics snapshot."""
        snapshot = MetricSnapshot(
            timestamp=time.time(),
            engagement_rate=self._calculate_engagement_rate(),
            user_satisfaction=self._calculate_satisfaction(),
            mode_accuracy=self._calculate_mode_accuracy(),
            avg_response_time=self._calculate_avg_response_time(),
            total_interactions=self._total_engagements,
        )

        self.history.append(snapshot)
        return snapshot

    def _calculate_engagement_rate(self) -> float:
        """Calculate engagement success rate."""
        if self._total_engagements == 0:
            return 0.0
        return self._successful_engagements / self._total_engagements

    def _calculate_satisfaction(self) -> float:
        """Calculate average user satisfaction."""
        if self._satisfaction_count == 0:
            return 0.0
        return self._total_satisfaction_score / self._satisfaction_count

    def _calculate_mode_accuracy(self) -> float:
        """Calculate mode selection accuracy."""
        if self._total_mode_selections == 0:
            return 0.0
        return self._correct_mode_selections / self._total_mode_selections

    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time."""
        if not self._response_times:
            return 0.0
        return sum(self._response_times) / len(self._response_times)

    def get_current_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        return {
            "engagement_rate": self._calculate_engagement_rate(),
            "user_satisfaction": self._calculate_satisfaction(),
            "mode_accuracy": self._calculate_mode_accuracy(),
            "avg_response_time": self._calculate_avg_response_time(),
            "total_interactions": self._total_engagements,
        }

    def check_alerts(self) -> list[dict[str, Any]]:
        """Check for performance alerts."""
        alerts = []

        if len(self.history) < self._alert_thresholds["degradation_window"]:
            return alerts

        recent = list(self.history)[-self._alert_thresholds["degradation_window"] :]

        # Check engagement rate
        current_engagement = recent[-1].engagement_rate
        if current_engagement < self._alert_thresholds["engagement_rate_min"]:
            alerts.append(
                {
                    "type": "low_engagement",
                    "severity": "warning",
                    "message": f"Engagement rate dropped to {current_engagement:.2%}",
                    "value": current_engagement,
                    "threshold": self._alert_thresholds["engagement_rate_min"],
                }
            )

        # Check satisfaction
        current_satisfaction = recent[-1].user_satisfaction
        if current_satisfaction < self._alert_thresholds["satisfaction_min"]:
            alerts.append(
                {
                    "type": "low_satisfaction",
                    "severity": "warning",
                    "message": f"User satisfaction dropped to {current_satisfaction:.2f}",
                    "value": current_satisfaction,
                    "threshold": self._alert_thresholds["satisfaction_min"],
                }
            )

        # Check for degradation trend
        if len(recent) >= 5:
            first_half = recent[: len(recent) // 2]
            second_half = recent[len(recent) // 2 :]

            first_engagement = sum(s.engagement_rate for s in first_half) / len(
                first_half
            )
            second_engagement = sum(s.engagement_rate for s in second_half) / len(
                second_half
            )

            if second_engagement < first_engagement * 0.8:  # 20% drop
                alerts.append(
                    {
                        "type": "degradation_trend",
                        "severity": "critical",
                        "message": f"Performance degrading: {first_engagement:.2%} → {second_engagement:.2%}",
                        "trend": "degrading",
                    }
                )

        return alerts

    def export_data(self, filepath: str) -> None:
        """Export metrics history to file."""
        data = {
            "snapshots": [s.to_dict() for s in self.history],
            "current_metrics": self.get_current_metrics(),
            "export_time": time.time(),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)


class ABTestFramework:
    """A/B testing framework for comparing strategies."""

    def __init__(self):
        self._variants: dict[str, dict] = {}
        self._user_assignments: dict[str, str] = {}  # user_id -> variant

    def create_test(
        self,
        test_name: str,
        variant_a: dict[str, Any],
        variant_b: dict[str, Any],
        traffic_split: float = 0.5,
    ) -> None:
        """Create a new A/B test.

        Args:
            test_name: Name of the test
            variant_a: Configuration for variant A (control)
            variant_b: Configuration for variant B (treatment)
            traffic_split: Percentage of traffic to variant B (0-1)
        """
        self._variants[test_name] = {
            "variant_a": variant_a,
            "variant_b": variant_b,
            "traffic_split": traffic_split,
            "metrics_a": {"engagements": 0, "successes": 0},
            "metrics_b": {"engagements": 0, "successes": 0},
        }

    def get_variant(self, test_name: str, user_id: str) -> dict[str, Any]:
        """Get variant assignment for a user.

        Args:
            test_name: Name of the test
            user_id: User to assign

        Returns:
            Variant configuration
        """
        if test_name not in self._variants:
            raise ValueError(f"Test '{test_name}' not found")

        # Check if user already assigned
        key = f"{test_name}:{user_id}"
        if key in self._user_assignments:
            variant_name = self._user_assignments[key]
            return self._variants[test_name][variant_name]

        # New assignment
        import hashlib

        hash_val = int(hashlib.md5(key.encode()).hexdigest(), 16)
        test = self._variants[test_name]

        if (hash_val % 100) < (test["traffic_split"] * 100):
            self._user_assignments[key] = "variant_b"
            return test["variant_b"]
        else:
            self._user_assignments[key] = "variant_a"
            return test["variant_a"]

    def record_result(
        self,
        test_name: str,
        user_id: str,
        success: bool,
    ) -> None:
        """Record result for a test."""
        if test_name not in self._variants:
            return

        key = f"{test_name}:{user_id}"
        variant_name = self._user_assignments.get(key, "variant_a")

        metrics = self._variants[test_name][f"metrics_{variant_name[-1]}"]
        metrics["engagements"] += 1
        if success:
            metrics["successes"] += 1

    def get_test_results(self, test_name: str) -> dict[str, Any]:
        """Get results for a test."""
        if test_name not in self._variants:
            return {}

        test = self._variants[test_name]

        def calc_rate(metrics):
            if metrics["engagements"] == 0:
                return 0.0
            return metrics["successes"] / metrics["engagements"]

        rate_a = calc_rate(test["metrics_a"])
        rate_b = calc_rate(test["metrics_b"])

        return {
            "test_name": test_name,
            "variant_a": {
                **test["metrics_a"],
                "success_rate": rate_a,
            },
            "variant_b": {
                **test["metrics_b"],
                "success_rate": rate_b,
            },
            "improvement": rate_b - rate_a,
            "relative_improvement": (rate_b - rate_a) / rate_a if rate_a > 0 else 0,
        }


# Global instances
_metrics_tracker: LearningMetricsTracker | None = None
_ab_framework: ABTestFramework | None = None


def get_metrics_tracker() -> LearningMetricsTracker:
    """Get global metrics tracker."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = LearningMetricsTracker()
    return _metrics_tracker


def get_ab_framework() -> ABTestFramework:
    """Get global A/B test framework."""
    global _ab_framework
    if _ab_framework is None:
        _ab_framework = ABTestFramework()
    return _ab_framework
