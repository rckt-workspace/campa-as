"""Configuration for content matching"""
from dataclasses import dataclass


@dataclass
class MatcherConfig:
    """Configuration for matching algorithm"""
    # Weights for similarity components
    visual_weight: float = 0.70
    caption_weight: float = 0.20
    type_weight: float = 0.07
    date_weight: float = 0.03

    # Thresholds for status determination
    found_threshold: float = 0.85
    review_threshold: float = 0.65

    def __post_init__(self):
        """Validate that weights sum to 1.0"""
        total = (
            self.visual_weight
            + self.caption_weight
            + self.type_weight
            + self.date_weight
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
