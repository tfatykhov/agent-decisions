"""
Calibration visualization using matplotlib.

Provides visual analysis of decision-making calibration:
- Reliability diagram (calibration curve)
- Brier score over time
- Confidence distribution
- Reason-type effectiveness
"""

from __future__ import annotations

import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Decision


@dataclass
class CalibrationBin:
    """A bin for calibration curve calculation."""

    predicted_mean: float
    actual_mean: float
    count: int


def calculate_calibration_bins(
    decisions: list[Decision],
    n_bins: int = 10,
) -> list[CalibrationBin]:
    """
    Calculate calibration bins for reliability diagram.

    Groups decisions by confidence into bins, then compares
    predicted confidence to actual success rate in each bin.

    Args:
        decisions: List of reviewed decisions with binary outcomes
        n_bins: Number of bins to use (default 10)

    Returns:
        List of CalibrationBin objects
    """
    # Filter to decisions with binary outcomes
    scored = [
        (d.confidence, d.outcome_binary)
        for d in decisions
        if d.outcome_binary is not None
    ]

    if not scored:
        return []

    # Create bins
    bins: dict[int, list[tuple[float, float]]] = defaultdict(list)

    for conf, outcome in scored:
        # Bin index from 0 to n_bins-1
        bin_idx = min(int(conf * n_bins), n_bins - 1)
        bins[bin_idx].append((conf, outcome))

    # Calculate mean predicted and actual for each bin
    result = []
    for bin_idx in range(n_bins):
        if bin_idx in bins and bins[bin_idx]:
            confs = [c for c, _ in bins[bin_idx]]
            outcomes = [o for _, o in bins[bin_idx]]
            result.append(
                CalibrationBin(
                    predicted_mean=sum(confs) / len(confs),
                    actual_mean=sum(outcomes) / len(outcomes),
                    count=len(confs),
                )
            )

    return result


def calculate_ece(
    decisions: list[Decision],
    n_bins: int = 10,
) -> float | None:
    """
    Calculate Expected Calibration Error (ECE).

    ECE = Σ (n_b / N) * |acc_b - conf_b|

    Where n_b is the number of samples in bin b, N is total samples,
    acc_b is accuracy in bin b, conf_b is mean confidence in bin b.

    Lower is better: 0 = perfect calibration.

    Args:
        decisions: List of reviewed decisions with binary outcomes
        n_bins: Number of bins to use

    Returns:
        ECE value (0-1) or None if no scored decisions
    """
    bins = calculate_calibration_bins(decisions, n_bins)

    if not bins:
        return None

    total_count = sum(b.count for b in bins)
    if total_count == 0:
        return None

    ece = sum(
        (b.count / total_count) * abs(b.actual_mean - b.predicted_mean)
        for b in bins
    )

    return ece


def calculate_brier_over_time(
    decisions: list[Decision],
    window_size: int = 5,
) -> list[tuple[datetime, float]]:
    """
    Calculate rolling Brier score over time.

    Args:
        decisions: List of decisions (will be sorted by timestamp)
        window_size: Number of decisions in rolling window

    Returns:
        List of (timestamp, brier_score) tuples
    """
    # Filter to reviewed decisions with binary outcomes, sorted by time
    reviewed = sorted(
        [d for d in decisions if d.outcome_binary is not None],
        key=lambda d: d.timestamp,
    )

    if len(reviewed) < window_size:
        return []

    result = []
    for i in range(window_size, len(reviewed) + 1):
        window = reviewed[i - window_size : i]
        brier = sum(
            (d.confidence - d.outcome_binary) ** 2 for d in window  # type: ignore
        ) / window_size
        result.append((reviewed[i - 1].timestamp, brier))

    return result


def calculate_reason_effectiveness(
    decisions: list[Decision],
) -> dict[str, dict[str, float]]:
    """
    Calculate effectiveness statistics by reason type.

    Returns dict mapping reason_type -> {
        'count': number of decisions using this reason type,
        'success_rate': success rate for decisions using this type,
        'avg_strength': average strength of reasons of this type,
        'avg_confidence': average confidence when using this type,
    }
    """
    from .models import Outcome, ReasonType

    # Track stats per reason type
    stats: dict[str, dict] = {}

    for rtype in ReasonType:
        stats[rtype.value] = {
            "decisions": [],  # List of (outcome, confidence, strength)
        }

    # Collect data
    for d in decisions:
        if d.outcome_binary is None:
            continue

        for reason in d.reasons:
            rtype = reason.reason_type.value
            stats[rtype]["decisions"].append(
                (d.outcome == Outcome.SUCCESS, d.confidence, reason.strength)
            )

    # Calculate stats
    result = {}
    for rtype, data in stats.items():
        dec_list = data["decisions"]
        if not dec_list:
            continue

        successes = sum(1 for success, _, _ in dec_list if success)
        result[rtype] = {
            "count": len(dec_list),
            "success_rate": successes / len(dec_list),
            "avg_strength": sum(s for _, _, s in dec_list) / len(dec_list),
            "avg_confidence": sum(c for _, c, _ in dec_list) / len(dec_list),
        }

    return result


def plot_calibration(
    decisions: list[Decision],
    output_path: str | Path | None = None,
    title: str = "Calibration Curve",
    show: bool = False,
) -> bytes | None:
    """
    Generate a reliability diagram (calibration curve).

    The diagonal line represents perfect calibration.
    Points above the line indicate overconfidence.
    Points below indicate underconfidence.

    Args:
        decisions: List of reviewed decisions
        output_path: Path to save the plot (PNG)
        title: Plot title
        show: If True, display the plot interactively

    Returns:
        PNG bytes if output_path is None and show is False
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for plotting. "
            "Install with: pip install agent-decisions[plots]"
        ) from e

    bins = calculate_calibration_bins(decisions)

    if not bins:
        return None

    fig, ax = plt.subplots(figsize=(8, 8))

    # Perfect calibration line
    ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration", alpha=0.7)

    # Calibration points
    predicted = [b.predicted_mean for b in bins]
    actual = [b.actual_mean for b in bins]
    counts = [b.count for b in bins]

    # Size points by count
    sizes = [max(50, min(500, c * 20)) for c in counts]

    scatter = ax.scatter(
        predicted,
        actual,
        s=sizes,
        alpha=0.7,
        c=predicted,
        cmap="viridis",
        edgecolors="black",
        linewidths=1,
    )

    # Add count labels
    for i, (x, y, c) in enumerate(zip(predicted, actual, counts)):
        ax.annotate(
            f"n={c}",
            (x, y),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=8,
        )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean Predicted Confidence", fontsize=12)
    ax.set_ylabel("Actual Success Rate", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(loc="lower right")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)

    # Determine overconfidence/underconfidence using raw decision data
    # (weighted properly by count, not unweighted bin means)
    scored = [
        (d.confidence, d.outcome_binary)
        for d in decisions
        if d.outcome_binary is not None
    ]
    if scored:
        total_pred = sum(c for c, _ in scored) / len(scored)
        total_actual = sum(o for _, o in scored) / len(scored)
    else:
        total_pred = sum(predicted) / len(predicted)
        total_actual = sum(actual) / len(actual)

    if total_pred > total_actual + 0.1:
        ax.text(
            0.05,
            0.95,
            "⚠️ Overconfident",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            color="red",
        )
    elif total_actual > total_pred + 0.1:
        ax.text(
            0.05,
            0.95,
            "✓ Underconfident",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            color="green",
        )

    # Add ECE metric
    ece = calculate_ece(decisions)
    if ece is not None:
        ax.text(
            0.95,
            0.05,
            f"ECE: {ece:.3f}",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="bottom",
            horizontalalignment="right",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return None
    elif show:
        plt.show()
        plt.close(fig)
        return None
    else:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()


def plot_brier_over_time(
    decisions: list[Decision],
    window_size: int = 5,
    output_path: str | Path | None = None,
    title: str = "Brier Score Over Time",
    show: bool = False,
) -> bytes | None:
    """
    Plot Brier score trend over time.

    Lower is better. 0 = perfect, 0.25 = random, 1 = always wrong.

    Args:
        decisions: List of decisions
        window_size: Rolling window size
        output_path: Path to save the plot (PNG)
        title: Plot title
        show: If True, display the plot interactively

    Returns:
        PNG bytes if output_path is None and show is False
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for plotting. "
            "Install with: pip install agent-decisions[plots]"
        ) from e

    data = calculate_brier_over_time(decisions, window_size)

    if not data:
        return None

    dates = [d for d, _ in data]
    scores = [s for _, s in data]

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(dates, scores, "b-", linewidth=2, marker="o", markersize=4)
    ax.fill_between(dates, scores, alpha=0.3)

    # Reference lines
    ax.axhline(y=0.25, color="orange", linestyle="--", alpha=0.7, label="Random (0.25)")
    ax.axhline(y=0.0, color="green", linestyle="--", alpha=0.7, label="Perfect (0.0)")

    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Brier Score (rolling window)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    # Set y limits
    ax.set_ylim(0, max(0.5, max(scores) * 1.1))

    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return None
    elif show:
        plt.show()
        plt.close(fig)
        return None
    else:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()


def plot_confidence_distribution(
    decisions: list[Decision],
    output_path: str | Path | None = None,
    title: str = "Confidence Distribution",
    show: bool = False,
) -> bytes | None:
    """
    Plot histogram of confidence levels, colored by outcome.

    Args:
        decisions: List of decisions
        output_path: Path to save the plot (PNG)
        title: Plot title
        show: If True, display the plot interactively

    Returns:
        PNG bytes if output_path is None and show is False
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for plotting. "
            "Install with: pip install agent-decisions[plots]"
        ) from e

    from .models import Outcome

    # Separate by outcome
    success_conf = [d.confidence for d in decisions if d.outcome == Outcome.SUCCESS]
    failure_conf = [d.confidence for d in decisions if d.outcome == Outcome.FAILURE]
    pending_conf = [d.confidence for d in decisions if d.is_pending]

    if not any([success_conf, failure_conf, pending_conf]):
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    bins = np.linspace(0, 1, 11)

    if success_conf:
        ax.hist(
            success_conf,
            bins=bins,
            alpha=0.7,
            label=f"Success (n={len(success_conf)})",
            color="green",
        )
    if failure_conf:
        ax.hist(
            failure_conf,
            bins=bins,
            alpha=0.7,
            label=f"Failure (n={len(failure_conf)})",
            color="red",
        )
    if pending_conf:
        ax.hist(
            pending_conf,
            bins=bins,
            alpha=0.5,
            label=f"Pending (n={len(pending_conf)})",
            color="gray",
        )

    ax.set_xlabel("Confidence Level", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_xlim(0, 1)

    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return None
    elif show:
        plt.show()
        plt.close(fig)
        return None
    else:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()


def plot_reason_effectiveness(
    decisions: list[Decision],
    output_path: str | Path | None = None,
    title: str = "Reason Type Effectiveness",
    show: bool = False,
) -> bytes | None:
    """
    Plot success rate by reason type (horizontal bar chart).

    Args:
        decisions: List of decisions
        output_path: Path to save the plot (PNG)
        title: Plot title
        show: If True, display the plot interactively

    Returns:
        PNG bytes if output_path is None and show is False
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for plotting. "
            "Install with: pip install agent-decisions[plots]"
        ) from e

    stats = calculate_reason_effectiveness(decisions)

    if not stats:
        return None

    # Sort by success rate
    sorted_types = sorted(stats.keys(), key=lambda x: stats[x]["success_rate"], reverse=True)

    fig, ax = plt.subplots(figsize=(10, max(6, len(sorted_types) * 0.6)))

    y_pos = np.arange(len(sorted_types))
    success_rates = [stats[t]["success_rate"] for t in sorted_types]
    counts = [stats[t]["count"] for t in sorted_types]

    # Color by success rate
    colors = plt.cm.RdYlGn([s for s in success_rates])  # type: ignore

    bars = ax.barh(y_pos, success_rates, color=colors, edgecolor="black", linewidth=0.5)

    # Add count labels
    for i, (bar, count) in enumerate(zip(bars, counts)):
        ax.text(
            bar.get_width() + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"n={count}",
            va="center",
            fontsize=9,
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(sorted_types)
    ax.set_xlabel("Success Rate", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlim(0, 1.15)
    ax.axvline(x=0.5, color="gray", linestyle="--", alpha=0.5, label="50% baseline")
    ax.grid(True, alpha=0.3, axis="x")

    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return None
    elif show:
        plt.show()
        plt.close(fig)
        return None
    else:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()


def plot_dashboard(
    decisions: list[Decision],
    output_path: str | Path | None = None,
    title: str = "Decision Calibration Dashboard",
    show: bool = False,
) -> bytes | None:
    """
    Generate a 2x2 dashboard with all calibration visualizations.

    Args:
        decisions: List of decisions
        output_path: Path to save the plot (PNG)
        title: Dashboard title
        show: If True, display the plot interactively

    Returns:
        PNG bytes if output_path is None and show is False
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import numpy as np
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for plotting. "
            "Install with: pip install agent-decisions[plots]"
        ) from e

    from .models import Outcome

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle(title, fontsize=16, fontweight="bold")

    # 1. Calibration curve (top-left)
    ax1 = axes[0, 0]
    bins = calculate_calibration_bins(decisions)

    ax1.plot([0, 1], [0, 1], "k--", label="Perfect", alpha=0.7)

    if bins:
        predicted = [b.predicted_mean for b in bins]
        actual = [b.actual_mean for b in bins]
        counts = [b.count for b in bins]
        sizes = [max(50, min(300, c * 15)) for c in counts]

        ax1.scatter(predicted, actual, s=sizes, alpha=0.7, c="blue", edgecolors="black")

    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1)
    ax1.set_xlabel("Predicted Confidence")
    ax1.set_ylabel("Actual Success Rate")
    ax1.set_title("Calibration Curve")
    ax1.set_aspect("equal")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="lower right")

    # 2. Brier score over time (top-right)
    ax2 = axes[0, 1]
    brier_data = calculate_brier_over_time(decisions)

    if brier_data:
        dates = [d for d, _ in brier_data]
        scores = [s for _, s in brier_data]

        ax2.plot(dates, scores, "b-", linewidth=2, marker="o", markersize=3)
        ax2.fill_between(dates, scores, alpha=0.3)
        ax2.axhline(y=0.25, color="orange", linestyle="--", alpha=0.7, label="Random")

        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax2.set_ylim(0, max(0.5, max(scores) * 1.1))
    else:
        ax2.text(0.5, 0.5, "Not enough data", ha="center", va="center", transform=ax2.transAxes)

    ax2.set_xlabel("Date")
    ax2.set_ylabel("Brier Score")
    ax2.set_title("Brier Score Over Time")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper right")

    # 3. Confidence distribution (bottom-left)
    ax3 = axes[1, 0]

    success_conf = [d.confidence for d in decisions if d.outcome == Outcome.SUCCESS]
    failure_conf = [d.confidence for d in decisions if d.outcome == Outcome.FAILURE]

    plot_bins = np.linspace(0, 1, 11)

    if success_conf:
        ax3.hist(success_conf, bins=plot_bins, alpha=0.7, label="Success", color="green")
    if failure_conf:
        ax3.hist(failure_conf, bins=plot_bins, alpha=0.7, label="Failure", color="red")

    ax3.set_xlabel("Confidence Level")
    ax3.set_ylabel("Count")
    ax3.set_title("Confidence Distribution by Outcome")
    ax3.legend(loc="upper left")
    ax3.grid(True, alpha=0.3, axis="y")
    ax3.set_xlim(0, 1)

    # 4. Reason effectiveness (bottom-right)
    ax4 = axes[1, 1]

    reason_stats = calculate_reason_effectiveness(decisions)

    if reason_stats:
        sorted_types = sorted(
            reason_stats.keys(), key=lambda x: reason_stats[x]["success_rate"], reverse=True
        )
        y_pos = np.arange(len(sorted_types))
        success_rates = [reason_stats[t]["success_rate"] for t in sorted_types]
        colors = plt.cm.RdYlGn(success_rates)  # type: ignore

        ax4.barh(y_pos, success_rates, color=colors, edgecolor="black", linewidth=0.5)
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(sorted_types, fontsize=9)
        ax4.axvline(x=0.5, color="gray", linestyle="--", alpha=0.5)
    else:
        ax4.text(0.5, 0.5, "No reason data", ha="center", va="center", transform=ax4.transAxes)

    ax4.set_xlabel("Success Rate")
    ax4.set_title("Reason Type Effectiveness")
    ax4.set_xlim(0, 1)
    ax4.grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return None
    elif show:
        plt.show()
        plt.close(fig)
        return None
    else:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
