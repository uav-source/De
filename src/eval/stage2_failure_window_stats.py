"""Strictly causal scalar window statistics for Stage 2 Day 9 diagnosis."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

import numpy as np


@dataclass(frozen=True)
class WindowStatisticConfig:
    window_size: int
    cusum_reference_sigma: float
    sign_zero_epsilon: float
    moment_epsilon: float

    def __post_init__(self) -> None:
        if isinstance(self.window_size, bool) or int(self.window_size) != self.window_size:
            raise ValueError("window_size must be an integer")
        if int(self.window_size) <= 0:
            raise ValueError("window_size must be positive")
        for name in [
            "cusum_reference_sigma",
            "sign_zero_epsilon",
            "moment_epsilon",
        ]:
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class SignalWindowStatistics:
    valid: bool
    window_count: int
    window_ready: bool
    consecutive_valid_count: int

    window_mean: float
    window_median: float
    window_energy: float

    positive_count: int
    negative_count: int
    zero_count: int
    dominant_sign_ratio: float

    current_sign: int
    current_same_sign_run_length: int
    max_same_sign_run_length: int

    lag1_autocorrelation: float
    skewness: float

    cusum_positive: float
    cusum_negative: float
    cusum_max: float
    cusum_signed: float


class CausalInnovationWindow:
    """Maintain one bounded, left-aligned causal innovation stream."""

    def __init__(self, config: WindowStatisticConfig):
        self._config = config
        self._values: Deque[float] = deque(maxlen=int(config.window_size))
        self._consecutive_valid_count = 0
        self._cusum_positive = 0.0
        self._cusum_negative = 0.0

    @property
    def config(self) -> WindowStatisticConfig:
        return self._config

    def reset(self) -> None:
        self._values.clear()
        self._consecutive_valid_count = 0
        self._cusum_positive = 0.0
        self._cusum_negative = 0.0

    def update(self, value: float, valid: bool) -> SignalWindowStatistics:
        if not bool(valid):
            self.reset()
            return _invalid_statistics()
        current = float(value)
        if not np.isfinite(current):
            raise ValueError("a valid innovation value must be finite")

        self._values.append(current)
        self._consecutive_valid_count += 1
        reference = float(self._config.cusum_reference_sigma)
        self._cusum_positive = max(
            0.0,
            self._cusum_positive + current - reference,
        )
        self._cusum_negative = max(
            0.0,
            self._cusum_negative - current - reference,
        )

        values = np.asarray(self._values, dtype=float)
        count = int(values.size)
        mean = float(np.mean(values))
        median = float(np.median(values))
        energy = float(np.mean(values * values))
        signs = np.asarray(
            [_classify_sign(item, self._config.sign_zero_epsilon) for item in values],
            dtype=int,
        )
        positive_count = int(np.count_nonzero(signs == 1))
        negative_count = int(np.count_nonzero(signs == -1))
        zero_count = int(np.count_nonzero(signs == 0))
        nonzero_count = positive_count + negative_count
        dominant_sign_ratio = (
            max(positive_count, negative_count) / nonzero_count
            if nonzero_count > 0
            else float("nan")
        )
        current_sign = int(signs[-1])
        current_run, maximum_run = _same_sign_runs(signs)
        autocorrelation = _lag1_autocorrelation(
            values,
            mean,
            float(self._config.moment_epsilon),
        )
        skewness = _population_skewness(
            values,
            mean,
            float(self._config.moment_epsilon),
        )
        cusum_max = max(self._cusum_positive, self._cusum_negative)
        cusum_signed = (
            self._cusum_positive
            if self._cusum_positive >= self._cusum_negative
            else -self._cusum_negative
        )
        return SignalWindowStatistics(
            valid=True,
            window_count=count,
            window_ready=count == int(self._config.window_size),
            consecutive_valid_count=self._consecutive_valid_count,
            window_mean=mean,
            window_median=median,
            window_energy=energy,
            positive_count=positive_count,
            negative_count=negative_count,
            zero_count=zero_count,
            dominant_sign_ratio=float(dominant_sign_ratio),
            current_sign=current_sign,
            current_same_sign_run_length=current_run,
            max_same_sign_run_length=maximum_run,
            lag1_autocorrelation=autocorrelation,
            skewness=skewness,
            cusum_positive=float(self._cusum_positive),
            cusum_negative=float(self._cusum_negative),
            cusum_max=float(cusum_max),
            cusum_signed=float(cusum_signed),
        )


def _invalid_statistics() -> SignalWindowStatistics:
    nan = float("nan")
    return SignalWindowStatistics(
        valid=False,
        window_count=0,
        window_ready=False,
        consecutive_valid_count=0,
        window_mean=nan,
        window_median=nan,
        window_energy=nan,
        positive_count=0,
        negative_count=0,
        zero_count=0,
        dominant_sign_ratio=nan,
        current_sign=0,
        current_same_sign_run_length=0,
        max_same_sign_run_length=0,
        lag1_autocorrelation=nan,
        skewness=nan,
        cusum_positive=nan,
        cusum_negative=nan,
        cusum_max=nan,
        cusum_signed=nan,
    )


def _classify_sign(value: float, epsilon: float) -> int:
    if float(value) > float(epsilon):
        return 1
    if float(value) < -float(epsilon):
        return -1
    return 0


def _same_sign_runs(signs: np.ndarray) -> tuple:
    current_sign = 0
    current_length = 0
    maximum_length = 0
    for raw_sign in np.asarray(signs, dtype=int):
        sign = int(raw_sign)
        if sign == 0:
            current_sign = 0
            current_length = 0
        elif sign == current_sign:
            current_length += 1
        else:
            current_sign = sign
            current_length = 1
        maximum_length = max(maximum_length, current_length)
    return current_length, maximum_length


def _lag1_autocorrelation(
    values: np.ndarray,
    mean: float,
    moment_epsilon: float,
) -> float:
    if values.size < 3:
        return float("nan")
    centered = values - float(mean)
    denominator = float(centered @ centered)
    if denominator <= float(moment_epsilon):
        return float("nan")
    numerator = float(centered[1:] @ centered[:-1])
    return numerator / denominator


def _population_skewness(
    values: np.ndarray,
    mean: float,
    moment_epsilon: float,
) -> float:
    if values.size < 3:
        return float("nan")
    centered = values - float(mean)
    second = float(np.mean(centered ** 2))
    if second <= float(moment_epsilon):
        return float("nan")
    third = float(np.mean(centered ** 3))
    return third / (second ** 1.5)
