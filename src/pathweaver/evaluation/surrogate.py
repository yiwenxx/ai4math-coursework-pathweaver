"""Domain-neutral multi-fidelity surrogate calibrator using pure-Python ridge regression."""
from collections.abc import Callable, Mapping, Sequence
import math
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class HighFidelityOracle(Protocol):
    """Domain-neutral high-fidelity oracle returning ground-truth scalar evaluations."""

    def measure(self, sample: Mapping[str, Any]) -> float:
        """Return a ground-truth scalar measurement for a sample."""
        ...


def _average_ranks(values: Sequence[float]) -> list[float]:
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i + 1
        while j < n and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = 0.5 * (i + 1 + j)
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def _pearson_correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in ys)
    if sxx <= 1e-15 or syy <= 1e-15:
        return None
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    corr = sxy / math.sqrt(sxx * syy)
    return round(max(-1.0, min(1.0, corr)), 6)


def _spearman_correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    return _pearson_correlation(_average_ranks(xs), _average_ranks(ys))


class SurrogateCalibrator:
    """Calibrates affine surrogate parameters (scale, shift) via ridge least squares."""

    MAX_FEATURES = 8

    def __init__(
        self,
        *,
        ridge_lambda: float = 1e-6,
        min_scale: float = 0.25,
        max_scale: float = 4.0,
    ) -> None:
        if not math.isfinite(ridge_lambda) or ridge_lambda < 0.0:
            raise ValueError("ridge_lambda must be finite and nonnegative")
        if not (math.isfinite(min_scale) and math.isfinite(max_scale) and 0.0 < min_scale <= max_scale):
            raise ValueError("trust region bounds must satisfy 0 < min_scale <= max_scale")
        self.ridge_lambda = float(ridge_lambda)
        self.min_scale = float(min_scale)
        self.max_scale = float(max_scale)
        self.scale: float = 1.0
        self.shift: float = 0.0

    def solve_ridge_least_squares(
        self,
        features: Sequence[Sequence[float]],
        targets: Sequence[float],
        *,
        ridge_lambda: float | None = None,
        unpenalized_indices: Sequence[int] = (),
    ) -> list[float]:
        """Solve (X^T X + Lambda) w = X^T y via Gauss-Jordan elimination for p <= 8."""
        n = len(features)
        if n != len(targets):
            raise ValueError("features and targets must have the same length")
        if n == 0:
            raise ValueError("cannot solve least squares with zero samples")
        p = len(features[0])
        if p < 1 or p > self.MAX_FEATURES:
            raise ValueError(f"ridge solver supports 1 <= p <= {self.MAX_FEATURES}, got p={p}")
        if any(len(row) != p for row in features):
            raise ValueError("inconsistent feature row width")

        lam = self.ridge_lambda if ridge_lambda is None else float(ridge_lambda)
        unpenalized = set(unpenalized_indices)

        # Form normal equations A = X^T X + Lambda, b = X^T y.
        aug = [[0.0] * (p + 1) for _ in range(p)]
        for row, target in zip(features, targets):
            y_val = float(target)
            for i in range(p):
                xi = float(row[i])
                aug[i][p] += xi * y_val
                for j in range(i, p):
                    aug[i][j] += xi * float(row[j])
        for i in range(p):
            for j in range(i):
                aug[i][j] = aug[j][i]
            if i not in unpenalized:
                aug[i][i] += lam

        # Gauss-Jordan elimination with partial pivoting.
        for col in range(p):
            pivot_row = max(range(col, p), key=lambda r: abs(aug[r][col]))
            if pivot_row != col:
                aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
            pivot = aug[col][col]
            if abs(pivot) < 1e-12:
                pivot = 1e-12 if pivot >= 0.0 else -1e-12
                aug[col][col] = pivot
            inv_pivot = 1.0 / pivot
            for j in range(col, p + 1):
                aug[col][j] *= inv_pivot
            for r in range(p):
                if r == col:
                    continue
                factor = aug[r][col]
                if factor != 0.0:
                    for j in range(col, p + 1):
                        aug[r][j] -= factor * aug[col][j]

        return [aug[i][p] for i in range(p)]

    def calibrate(
        self,
        surrogate_values: Sequence[float],
        ground_truth_values: Sequence[float],
    ) -> dict[str, Any]:
        """Fit residual y - x ~= delta_scale * x + shift with bounded trust-region clamping."""
        if len(surrogate_values) != len(ground_truth_values):
            raise ValueError("surrogate_values and ground_truth_values must have equal length")
        surr = [float(v) for v in surrogate_values]
        truth = [float(v) for v in ground_truth_values]
        if any(not math.isfinite(v) for v in surr) or any(not math.isfinite(v) for v in truth):
            raise ValueError("calibration inputs must be finite")

        n = len(surr)
        if n == 0:
            self.scale = 1.0
            self.shift = 0.0
            return {
                "scale": 1.0,
                "shift": 0.0,
                "raw_scale": 1.0,
                "clamped": False,
                "samples": 0,
                "mae_before": 0.0,
                "mae_after": 0.0,
                "rmse_before": 0.0,
                "rmse_after": 0.0,
                "rank_correlation_before": None,
                "rank_correlation_after": None,
                "rank_correlation": None,
                "pearson_before": None,
                "pearson_after": None,
            }

        residuals = [t - s for s, t in zip(surr, truth)]
        design = [[s, 1.0] for s in surr]
        delta_scale, _ = self.solve_ridge_least_squares(
            design,
            residuals,
            unpenalized_indices=(1,),
        )
        raw_scale = 1.0 + delta_scale
        scale = max(self.min_scale, min(self.max_scale, raw_scale))
        clamped = scale != raw_scale
        shift = (sum(truth) - scale * sum(surr)) / n

        calibrated = [scale * s + shift for s in surr]
        mae_before = sum(abs(s - t) for s, t in zip(surr, truth)) / n
        mae_after = sum(abs(c - t) for c, t in zip(calibrated, truth)) / n
        rmse_before = math.sqrt(sum((s - t) ** 2 for s, t in zip(surr, truth)) / n)
        rmse_after = math.sqrt(sum((c - t) ** 2 for c, t in zip(calibrated, truth)) / n)

        rank_before = _spearman_correlation(surr, truth)
        rank_after = _spearman_correlation(calibrated, truth)
        pearson_before = _pearson_correlation(surr, truth)
        pearson_after = _pearson_correlation(calibrated, truth)

        self.scale = scale
        self.shift = shift
        return {
            "scale": round(scale, 6),
            "shift": round(shift, 6),
            "raw_scale": round(raw_scale, 6),
            "clamped": clamped,
            "samples": n,
            "mae_before": round(mae_before, 6),
            "mae_after": round(mae_after, 6),
            "rmse_before": round(rmse_before, 6),
            "rmse_after": round(rmse_after, 6),
            "rank_correlation_before": rank_before,
            "rank_correlation_after": rank_after,
            "rank_correlation": rank_after,
            "pearson_before": pearson_before,
            "pearson_after": pearson_after,
        }

    def calibrate_with_oracle(
        self,
        samples: Sequence[Mapping[str, Any]],
        oracle: HighFidelityOracle,
        surrogate_fn: Callable[[Mapping[str, Any]], float],
    ) -> dict[str, Any]:
        """Query an oracle and surrogate function across samples and calibrate parameters."""
        surr = [float(surrogate_fn(item)) for item in samples]
        truth = [float(oracle.measure(item)) for item in samples]
        return self.calibrate(surr, truth)

    def predict(self, surrogate_value: float) -> float:
        """Apply calibrated affine transform to a surrogate prediction."""
        return self.scale * float(surrogate_value) + self.shift
