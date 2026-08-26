"""Second AgentShield risk signal: purchase synchronization per one-second window."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys


# These thresholds are deliberately gradual so small bursts of legitimate demand
# are not treated as critical. They are named to make future tuning simple.
LOW_AGENT_LIMIT = 2
MEDIUM_AGENT_LIMIT = 5
HIGH_AGENT_LIMIT = 19
CRITICAL_AGENT_THRESHOLD = 20
MAX_FAILURE_ADJUSTMENT = 5
MAX_NON_CRITICAL_SCORE = 74


@dataclass
class SynchronizationResult:
    """Purchase synchronization activity and risk assessment for one second."""

    window_start: datetime
    purchase_attempts: int
    unique_agents: int
    successful_purchases: int
    failed_purchases: int
    synchronization_score: int
    risk_score: int
    risk_level: str


def calculate_risk_score(unique_agents, purchase_attempts, failed_purchases):
    """Return a simple 0-100 synchronization risk score.

    Scores increase gradually: 1-2 agents are LOW, 3-5 are MEDIUM, 6-19 can
    reach MEDIUM or HIGH, and CRITICAL begins at 20 distinct agents in a second.
    Failed attempts add at most 5 points and cannot make a group below 20 agents
    CRITICAL. Synchronization alone is not proof of malicious behavior.
    """
    if unique_agents <= LOW_AGENT_LIMIT:
        agent_points = unique_agents * 10
    elif unique_agents <= MEDIUM_AGENT_LIMIT:
        agent_points = 25 + (unique_agents - 3) * 5
    elif unique_agents <= HIGH_AGENT_LIMIT:
        agent_points = 40 + (unique_agents - 6) * 2
    else:
        agent_points = 75 + (unique_agents - CRITICAL_AGENT_THRESHOLD) * 2

    failed_ratio = failed_purchases / purchase_attempts
    failure_adjustment = min(
        MAX_FAILURE_ADJUSTMENT, round(failed_ratio * MAX_FAILURE_ADJUSTMENT)
    )
    risk_score = min(100, agent_points + failure_adjustment)

    # Failed attempts are secondary: fewer than 20 agents can never be CRITICAL.
    if unique_agents < CRITICAL_AGENT_THRESHOLD:
        return min(MAX_NON_CRITICAL_SCORE, risk_score)
    return risk_score


def classify_risk(risk_score):
    """Convert a numeric score into a beginner-friendly risk level."""
    if risk_score < 25:
        return "LOW"
    if risk_score < 50:
        return "MEDIUM"
    if risk_score < 75:
        return "HIGH"
    return "CRITICAL"


def analyze_purchase_synchronization(events):
    """Analyze PURCHASE events grouped into fixed one-second timestamp windows."""
    windows = defaultdict(
        lambda: {"attempts": 0, "agents": set(), "successful": 0, "failed": 0}
    )

    for event in events:
        if event.action != "PURCHASE":
            continue

        # Removing microseconds places each event inside its containing second.
        window_start = event.timestamp.replace(microsecond=0)
        window = windows[window_start]
        window["attempts"] += 1
        window["agents"].add(event.agent_id)

        if event.inventory_after < event.inventory_before:
            window["successful"] += 1
        else:
            window["failed"] += 1

    results = []
    for window_start in sorted(windows):
        window = windows[window_start]
        unique_agents = len(window["agents"])
        # Synchronization is simply the count of different agents in this second.
        synchronization_score = unique_agents
        risk_score = calculate_risk_score(
            unique_agents, window["attempts"], window["failed"]
        )
        results.append(
            SynchronizationResult(
                window_start=window_start,
                purchase_attempts=window["attempts"],
                unique_agents=unique_agents,
                successful_purchases=window["successful"],
                failed_purchases=window["failed"],
                synchronization_score=synchronization_score,
                risk_score=risk_score,
                risk_level=classify_risk(risk_score),
            )
        )

    return results


def print_top_windows(results, limit=10):
    """Print the windows with the most different agents purchasing together."""
    top_windows = sorted(
        results,
        key=lambda result: (-result.synchronization_score, result.window_start),
    )[:limit]

    print("Top 10 highest-synchronization purchase windows")
    for result in top_windows:
        print(
            f"{result.window_start.isoformat(sep=' ')} | "
            f"attempts={result.purchase_attempts} | "
            f"unique_agents={result.unique_agents} | "
            f"successful={result.successful_purchases} | "
            f"failed={result.failed_purchases} | "
            f"synchronization={result.synchronization_score} | "
            f"risk={result.risk_score} | {result.risk_level}"
        )


def run_demo():
    """Run the existing simulator, analyze its events, and print the top windows."""
    repository_root = Path(__file__).resolve().parents[1]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    from simulator.simulator import SupermarketSimulation, create_agents

    simulation = SupermarketSimulation()
    events = simulation.run(create_agents())
    results = analyze_purchase_synchronization(events)
    print_top_windows(results)
    print("\nSynchronization is one risk signal and does not by itself prove malicious behavior.")
    return results


if __name__ == "__main__":
    run_demo()
