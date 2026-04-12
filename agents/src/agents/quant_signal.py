"""Quantitative signal agent.

Transforms textual analysis outputs (sentiment scores, regime classifications,
guidance directions) into structured quantitative signals suitable for
portfolio construction and risk management.
"""


import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src.core.agent import AgentMessage, AgentResponse, BaseAgent

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Signal:
    """A single quantitative signal derived from textual analysis."""

    name: str
    value: Decimal  # normalized [-1, 1]
    confidence: Decimal  # [0, 1]
    source: str  # e.g., "earnings_interpreter", "macro_regime"
    timestamp: str  # ISO date
    raw_value: Decimal  # pre-normalization value


@dataclass
class CompositeScore:
    """Weighted composite of multiple signals."""

    name: str
    score: Decimal  # weighted composite [-1, 1]
    components: list[Signal] = field(default_factory=list)
    method: str = "confidence_weight"


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

_REGIME_MAP: dict[str, tuple[Decimal, Decimal]] = {
    "EXPANSION": (Decimal("1"), Decimal("0.8")),
    "CONTRACTION": (Decimal("-1"), Decimal("0.8")),
    "TRANSITION": (Decimal("0"), Decimal("0.4")),
}

_GUIDANCE_MAP: dict[str, Decimal] = {
    "RAISED": Decimal("1"),
    "LOWERED": Decimal("-1"),
    "MAINTAINED": Decimal("0"),
    "NEUTRAL": Decimal("0"),
}


def normalize_signal(
    value: Decimal, min_val: Decimal, max_val: Decimal
) -> Decimal:
    """Normalize *value* into the [-1, 1] range and clamp to bounds.

    Args:
        value: The raw value to normalize.
        min_val: The minimum of the input range.
        max_val: The maximum of the input range.

    Returns:
        A Decimal in [-1, 1].
    """
    if max_val == min_val:
        return Decimal("0")
    normalized = (value - min_val) / (max_val - min_val) * 2 - 1
    return max(Decimal("-1"), min(Decimal("1"), normalized))


def compute_zscore(
    value: Decimal, mean: Decimal, std: Decimal
) -> Decimal:
    """Compute the standard z-score.

    Args:
        value: The observed value.
        mean: Population / sample mean.
        std: Standard deviation.

    Returns:
        The z-score, or ``Decimal("0")`` when *std* is zero.
    """
    if std == 0:
        return Decimal("0")
    return (value - mean) / std


def sentiment_to_signal(
    score: Decimal, label: str, source: str
) -> Signal:
    """Convert a sentiment score to a Signal.

    Args:
        score: Sentiment value, typically in [-1, 1].
        label: Descriptive label for the signal.
        source: Originating agent or module.

    Returns:
        A Signal with confidence derived from the absolute value of score.
    """
    clamped = max(Decimal("-1"), min(Decimal("1"), score))
    confidence = min(Decimal("1"), abs(clamped))
    return Signal(
        name=label,
        value=clamped,
        confidence=confidence,
        source=source,
        timestamp=datetime.now(tz=UTC).date().isoformat(),
        raw_value=score,
    )


def regime_to_signal(regime: str, source: str) -> Signal:
    """Map a macro-regime label to a Signal.

    Args:
        regime: One of ``"EXPANSION"``, ``"CONTRACTION"``, or
            ``"TRANSITION"``.
        source: Originating agent or module.

    Returns:
        A Signal whose value and confidence are determined by the regime.

    Raises:
        ValueError: If *regime* is not recognised.
    """
    key = regime.upper()
    if key not in _REGIME_MAP:
        raise ValueError(f"Unknown regime: {regime!r}")
    value, confidence = _REGIME_MAP[key]
    return Signal(
        name=f"regime_{key.lower()}",
        value=value,
        confidence=confidence,
        source=source,
        timestamp=datetime.now(tz=UTC).date().isoformat(),
        raw_value=value,
    )


def guidance_to_signal(direction: str, source: str) -> Signal:
    """Convert an earnings-guidance direction to a Signal.

    Args:
        direction: One of ``"RAISED"``, ``"LOWERED"``, ``"MAINTAINED"``,
            or ``"NEUTRAL"``.
        source: Originating agent or module.

    Returns:
        A Signal with value mapped from the direction string.

    Raises:
        ValueError: If *direction* is not recognised.
    """
    key = direction.upper()
    if key not in _GUIDANCE_MAP:
        raise ValueError(f"Unknown guidance direction: {direction!r}")
    value = _GUIDANCE_MAP[key]
    confidence = Decimal("0.7") if value != 0 else Decimal("0.3")
    return Signal(
        name=f"guidance_{key.lower()}",
        value=value,
        confidence=confidence,
        source=source,
        timestamp=datetime.now(tz=UTC).date().isoformat(),
        raw_value=value,
    )


def composite_score(
    signals: list[Signal],
    method: str = "confidence_weight",
) -> CompositeScore:
    """Combine multiple signals into a single composite score.

    Args:
        signals: List of Signal instances to combine.
        method: Aggregation strategy — ``"equal_weight"`` or
            ``"confidence_weight"``.

    Returns:
        A CompositeScore containing the weighted result.

    Raises:
        ValueError: If *signals* is empty or *method* is unknown.
    """
    if not signals:
        raise ValueError("Cannot compute composite from empty signal list")

    if method == "equal_weight":
        total = sum(s.value for s in signals)
        score = total / Decimal(len(signals))
    elif method == "confidence_weight":
        weighted_sum = sum(s.value * s.confidence for s in signals)
        weight_total = sum(s.confidence for s in signals)
        if weight_total == 0:
            score = Decimal("0")
        else:
            score = weighted_sum / weight_total
    else:
        raise ValueError(f"Unknown composite method: {method!r}")

    return CompositeScore(
        name="composite",
        score=score,
        components=list(signals),
        method=method,
    )


def decay_weight(age_days: int, half_life: int = 30) -> Decimal:
    """Exponential decay weight for signal freshness.

    Args:
        age_days: Age of the signal in days.
        half_life: Number of days until the weight halves.

    Returns:
        A Decimal weight in (0, 1].
    """
    exponent = -age_days / half_life
    return Decimal(str(math.pow(2, exponent)))


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class QuantSignalAgent(BaseAgent):
    """Agent that transforms textual insights into quantitative signals."""

    def __init__(self) -> None:
        super().__init__(
            name="quant_signal",
            description=(
                "Transforms qualitative analysis outputs into normalised "
                "quantitative signals and composite scores for systematic "
                "portfolio construction."
            ),
        )

    @property
    def system_prompt(self) -> str:
        """Return the system prompt for the quant signal agent."""
        return (
            "You are a quantitative signal extraction engine. Your role is "
            "to convert qualitative financial analysis — sentiment scores, "
            "macro-regime classifications, and earnings-guidance directions "
            "— into normalised quantitative signals on a [-1, 1] scale. "
            "Each signal carries a confidence weight and provenance metadata. "
            "You support composite scoring via equal-weight and "
            "confidence-weighted aggregation, as well as time-decay "
            "adjustments for signal freshness. Always output structured "
            "signal objects with full traceability back to the source agent."
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Process a prompt and return quantitative signals.

        Args:
            prompt: Natural-language request describing the signals to
                extract or combine.
            **kwargs: Additional context (e.g. ``signals``, ``regime``,
                ``sentiment``).

        Returns:
            An AgentResponse containing signal analysis results.
        """
        self.add_to_history(AgentMessage(role="user", content=prompt))
        signals: list[Signal] = []
        metadata: dict[str, Any] = {"agent": self.name}

        if "sentiment" in kwargs:
            sig = sentiment_to_signal(
                Decimal(str(kwargs["sentiment"])),
                label="sentiment",
                source=kwargs.get("source", "unknown"),
            )
            signals.append(sig)

        if "regime" in kwargs:
            sig = regime_to_signal(
                kwargs["regime"],
                source=kwargs.get("source", "unknown"),
            )
            signals.append(sig)

        if "direction" in kwargs:
            sig = guidance_to_signal(
                kwargs["direction"],
                source=kwargs.get("source", "unknown"),
            )
            signals.append(sig)

        if "signals" in kwargs:
            signals.extend(kwargs["signals"])

        if signals:
            method = kwargs.get("method", "confidence_weight")
            comp = composite_score(signals, method=method)
            metadata["composite"] = {
                "score": str(comp.score),
                "method": comp.method,
                "n_signals": len(comp.components),
            }
            metadata["signals"] = [
                {
                    "name": s.name,
                    "value": str(s.value),
                    "confidence": str(s.confidence),
                    "source": s.source,
                }
                for s in signals
            ]
            content = (
                f"Composite score ({comp.method}): {comp.score}\n"
                f"Components: {len(signals)} signals processed."
            )
        else:
            content = (
                "No structured inputs provided. Pass sentiment, regime, "
                "direction, or signals via kwargs to generate quantitative "
                "signals."
            )

        self.add_to_history(AgentMessage(role="assistant", content=content))
        return AgentResponse(content=content, metadata=metadata)
