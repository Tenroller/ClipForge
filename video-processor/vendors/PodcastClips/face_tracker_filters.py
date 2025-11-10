"""
Advanced filtering algorithms for face tracking temporal consistency.

Implements One-Euro filter and other smoothing techniques for jitter-free camera motion.
"""

import numpy as np
from typing import Optional
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.face_tracker_filters")


class OneEuroFilter:
    """
    One-Euro filter for smooth tracking with low lag.

    The One-Euro filter adapts its smoothing based on signal velocity:
    - Fast movements: Less smoothing (low lag, more responsive)
    - Slow movements: More smoothing (removes jitter)

    This is ideal for camera tracking where you want smooth motion
    without the lag that comes from heavy filtering.

    Reference: "1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input"
    https://cristal.univ-lille.fr/~casiez/1euro/
    """

    def __init__(
        self,
        freq: float = 30.0,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0
    ):
        """
        Initialize One-Euro filter.

        Args:
            freq: Expected update frequency in Hz (e.g., 30 for 30fps video)
            min_cutoff: Minimum cutoff frequency (lower = more smoothing)
                       - 0.5: Very smooth, more lag
                       - 1.0: Balanced (recommended)
                       - 2.0: More responsive, less smooth
            beta: Speed coefficient (how much to adapt to velocity)
                 - 0.001: Low adaptation (consistent smoothing)
                 - 0.007: Balanced (recommended)
                 - 0.01: High adaptation (follows fast motion closely)
            d_cutoff: Derivative cutoff frequency (typically 1.0)
        """
        self.freq = freq
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        # Filter state
        self.x_prev: Optional[float] = None
        self.dx_prev: float = 0.0
        self.timestamp_prev: Optional[float] = None

    def reset(self):
        """Reset filter state."""
        self.x_prev = None
        self.dx_prev = 0.0
        self.timestamp_prev = None

    def _smoothing_factor(self, t_e: float, cutoff: float) -> float:
        """
        Calculate exponential smoothing factor.

        Args:
            t_e: Time elapsed since last update
            cutoff: Cutoff frequency

        Returns:
            Smoothing factor alpha (0-1)
        """
        r = 2 * np.pi * cutoff * t_e
        return r / (r + 1)

    def _exponential_smoothing(self, a: float, x: float, x_prev: float) -> float:
        """
        Apply exponential smoothing.

        Args:
            a: Smoothing factor (0-1)
            x: Current value
            x_prev: Previous filtered value

        Returns:
            Smoothed value
        """
        return a * x + (1 - a) * x_prev

    def __call__(self, x: float, timestamp: Optional[float] = None) -> float:
        """
        Filter a new value.

        Args:
            x: Input value to filter
            timestamp: Optional timestamp in seconds (if None, uses 1/freq)

        Returns:
            Filtered value
        """
        # First call - initialize
        if self.x_prev is None:
            self.x_prev = x
            self.timestamp_prev = timestamp if timestamp is not None else 0.0
            return x

        # Calculate time elapsed
        if timestamp is not None and self.timestamp_prev is not None:
            t_e = timestamp - self.timestamp_prev
        else:
            t_e = 1.0 / self.freq

        # Avoid division by zero
        if t_e <= 0:
            t_e = 1.0 / self.freq

        # Estimate current derivative
        dx = (x - self.x_prev) / t_e

        # Smooth derivative
        a_d = self._smoothing_factor(t_e, self.d_cutoff)
        dx_hat = self._exponential_smoothing(a_d, dx, self.dx_prev)

        # Calculate adaptive cutoff based on velocity
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)

        # Smooth the value
        a = self._smoothing_factor(t_e, cutoff)
        x_hat = self._exponential_smoothing(a, x, self.x_prev)

        # Store state for next call
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.timestamp_prev = timestamp

        return x_hat


class LowPassFilter:
    """
    Simple low-pass filter for comparison.

    Less sophisticated than One-Euro but simpler and still effective.
    """

    def __init__(self, alpha: float = 0.5):
        """
        Initialize low-pass filter.

        Args:
            alpha: Smoothing factor (0-1)
                  - 0.1: Very smooth, high lag
                  - 0.5: Balanced
                  - 0.9: Minimal smoothing, low lag
        """
        self.alpha = alpha
        self.x_prev: Optional[float] = None

    def reset(self):
        """Reset filter state."""
        self.x_prev = None

    def __call__(self, x: float) -> float:
        """Filter a new value."""
        if self.x_prev is None:
            self.x_prev = x
            return x

        x_filtered = self.alpha * x + (1 - self.alpha) * self.x_prev
        self.x_prev = x_filtered
        return x_filtered


class DoubleExponentialFilter:
    """
    Double exponential smoothing filter.

    Accounts for trend in the data for better prediction.
    """

    def __init__(self, alpha: float = 0.5, beta: float = 0.3):
        """
        Initialize double exponential filter.

        Args:
            alpha: Level smoothing factor (0-1)
            beta: Trend smoothing factor (0-1)
        """
        self.alpha = alpha
        self.beta = beta
        self.s_prev: Optional[float] = None  # Level
        self.b_prev: float = 0.0  # Trend

    def reset(self):
        """Reset filter state."""
        self.s_prev = None
        self.b_prev = 0.0

    def __call__(self, x: float) -> float:
        """Filter a new value."""
        if self.s_prev is None:
            self.s_prev = x
            return x

        # Update level
        s = self.alpha * x + (1 - self.alpha) * (self.s_prev + self.b_prev)

        # Update trend
        b = self.beta * (s - self.s_prev) + (1 - self.beta) * self.b_prev

        # Store for next iteration
        self.s_prev = s
        self.b_prev = b

        # Return smoothed value with trend
        return s + b


def smooth_trajectory_with_one_euro(
    timestamps: np.ndarray,
    positions: np.ndarray,
    fps: float = 30.0,
    min_cutoff: float = 1.0,
    beta: float = 0.007
) -> np.ndarray:
    """
    Apply One-Euro filter to a complete trajectory.

    Args:
        timestamps: Array of timestamps in seconds
        positions: Array of position values (e.g., x-coordinates)
        fps: Video frame rate
        min_cutoff: Minimum cutoff frequency (lower = smoother)
        beta: Speed coefficient (higher = more adaptive)

    Returns:
        Smoothed positions array
    """
    if len(timestamps) == 0:
        return positions

    filter = OneEuroFilter(freq=fps, min_cutoff=min_cutoff, beta=beta)
    smoothed = np.zeros_like(positions)

    for i, (t, x) in enumerate(zip(timestamps, positions)):
        smoothed[i] = filter(x, timestamp=t)

    return smoothed
