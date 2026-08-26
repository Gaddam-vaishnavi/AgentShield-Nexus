"""First AgentShield risk signal: purchase velocity per one-second window."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys


@dataclass
class VelocityResult:
    """The purchase activity and velocity risk assessment for one second."""

    window_start: datetime
    purchase_attempts: int
    successful_purchases: int
    failed_purchases: int
    velocity: int
    risk_score: int
    risk_level: str


def calculate_risk_score(purchase_attempts, failed_purchases):
    """Return a simple 0-100 score based on velocity and failed attempts.

    Each purchase attempt in a second contributes 15 points, up to 80 points.
    Failed attempts add up to 20 more points based on their share of attempts.
    This is only a screening signal: high velocity does not prove malicious intent.
    """
    velocity_points = min(80, purchase_attempts * 15)
    failed_ratio = failed_purchases / purchase_attempts
    failure_points = round(failed_ratio * 20)
    return min(100, velocity_points + failure_points)


def classify_risk(risk_score):
    """Convert the simple numeric score into a readable risk level."""
    if risk_score < 25:
        return "LOW"
    if risk_score < 50:
        return "MEDIUM"
    if risk_score < 75:
        return "HIGH"
    return "CRITICAL"


def analyze_purchase_velocity(events):
    """Analyze PURCHASE events from the simulator in fixed one-second windows.

    A purchase is successful when its inventory falls during that event. This
    matches the Event representation produced by the simulator's timeline replay.
    """
    windows = defaultdict(lambda: {"attempts": 0, "successful": 0, "failed": 0})

    for event in events:
        if event.action != "PURCHASE":
            continue

        # Removing microseconds places every timestamp in its containing second.
        window_start = event.timestamp.replace(microsecond=0)
        window = windows[window_start]
        window["attempts"] += 1

        if event.inventory_after < event.inventory_before:
            window["successful"] += 1
        else:
            window["failed"] += 1

    results = []
    for window_start in sorted(windows):
        window = windows[window_start]
        velocity = window["attempts"]  # Each window is exactly one second long.
        risk_score = calculate_risk_score(velocity, window["failed"])
        results.append(
            VelocityResult(
                window_start=window_start,
                purchase_attempts=window["attempts"],
                successful_purchases=window["successful"],
                failed_purchases=window["failed"],
                velocity=velocity,
                risk_score=risk_score,
                risk_level=classify_risk(risk_score),
            )
        )

    return results


def print_top_windows(results, limit=10):
    """Print the highest-velocity results, breaking ties by earliest window."""
    top_windows = sorted(
        results, key=lambda result: (-result.velocity, result.window_start)
    )[:limit]

    print("Top 10 highest-velocity purchase windows")
    for result in top_windows:
        print(
            f"{result.window_start.isoformat(sep=' ')} | "
            f"attempts={result.purchase_attempts} | "
            f"successful={result.successful_purchases} | "
            f"failed={result.failed_purchases} | "
            f"velocity={result.velocity}/sec | "
            f"score={result.risk_score} | {result.risk_level}"
        )


def run_demo():
    """Run the existing simulator, analyze its events, and print the top windows."""
    repository_root = Path(__file__).resolve().parents[1]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    from simulator.simulator import SupermarketSimulation, create_agents

    simulation = SupermarketSimulation()
    events = simulation.run(create_agents())
    results = analyze_purchase_velocity(events)
    print_top_windows(results)
    print("\nVelocity is one risk signal and does not by itself prove malicious behavior.")
    return results


if __name__ == "__main__":
    run_demo()
