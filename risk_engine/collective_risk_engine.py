"""Central, transparent collective-risk scoring for the AgentShield prototype."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys


# Allow this file to run directly while reusing the existing detector modules.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from risk_engine.behavior_detector import find_similar_behavior_groups
from risk_engine.inventory_impact_detector import analyze_inventory_impact
from risk_engine.synchronization_detector import analyze_purchase_synchronization
from risk_engine.velocity_detector import analyze_purchase_velocity


# The weights add to 1.0 (100%) and can be tuned as AgentShield evolves.
VELOCITY_WEIGHT = 0.25
SYNCHRONIZATION_WEIGHT = 0.25
INVENTORY_IMPACT_WEIGHT = 0.30
BEHAVIOR_COORDINATION_WEIGHT = 0.20

# Overall risk levels and multi-signal safeguard thresholds.
LOW_RISK_MAX_SCORE = 25
MEDIUM_RISK_MAX_SCORE = 50
HIGH_RISK_MAX_SCORE = 75
STRONG_SIGNAL_SCORE = 60
MIN_SIGNALS_FOR_HIGH_RISK = 2
MIN_SIGNALS_FOR_CRITICAL_RISK = 3


@dataclass
class CollectiveRiskResult:
    """Combined risk assessment for one fixed one-second purchase window."""

    window_start: datetime
    velocity_score: int
    synchronization_score: int
    inventory_impact_score: int
    behavior_coordination_score: int
    overall_risk_score: int
    overall_risk_level: str
    reason: str


def classify_overall_risk(score):
    """Convert the combined 0-100 score into a configurable risk level."""
    if score < LOW_RISK_MAX_SCORE:
        return "LOW"
    if score < MEDIUM_RISK_MAX_SCORE:
        return "MEDIUM"
    if score < HIGH_RISK_MAX_SCORE:
        return "HIGH"
    return "CRITICAL"


def build_behavior_scores_by_agent(groups):
    """Map each observed group member to its highest group coordination score."""
    scores_by_agent = {}
    for group in groups:
        for agent_id in group.agent_ids:
            scores_by_agent[agent_id] = max(
                scores_by_agent.get(agent_id, 0), group.coordination_score
            )
    return scores_by_agent


def build_behavior_scores_by_window(events, scores_by_agent):
    """Give a purchase second the highest behavior score of agents active in it."""
    scores_by_window = {}
    for event in events:
        if event.action != "PURCHASE":
            continue
        window_start = event.timestamp.replace(microsecond=0)
        agent_score = scores_by_agent.get(event.agent_id, 0)
        scores_by_window[window_start] = max(
            scores_by_window.get(window_start, 0), agent_score
        )
    return scores_by_window


def build_reason(scores):
    """Return a short explanation containing the strongest observed signals."""
    labels = {
        "velocity": "unusually high purchase velocity",
        "synchronization": "many unique agents acting together",
        "inventory": "significant collective inventory pressure",
        "behavior": "highly similar, tightly timed purchase behavior",
    }
    strongest = [
        labels[name]
        for name, score in sorted(scores.items(), key=lambda item: -item[1])
        if score >= STRONG_SIGNAL_SCORE
    ]
    if not strongest:
        return "No individual signal crossed the strong-signal threshold."
    return "; ".join(strongest)


def apply_contextual_safeguards(weighted_score, signal_scores):
    """
    Prevent isolated behavioral similarity or velocity from creating
    an unnecessarily high collective-risk result.

    HIGH risk requires:
    - at least two strong signals, AND
    - meaningful synchronization or inventory pressure.

    CRITICAL risk requires:
    - at least three strong signals, AND
    - meaningful inventory pressure.

    This helps separate normal popular-product activity from
    genuine collective inventory pressure.
    """

    strong_signal_count = sum(
        score >= STRONG_SIGNAL_SCORE
        for score in signal_scores.values()
    )

    synchronization_strong = (
        signal_scores["synchronization"] >= STRONG_SIGNAL_SCORE
    )

    inventory_strong = (
        signal_scores["inventory"] >= STRONG_SIGNAL_SCORE
    )

    # High velocity + high behavior similarity alone
    # should not be enough for HIGH risk.
    if strong_signal_count < MIN_SIGNALS_FOR_HIGH_RISK:
        return min(weighted_score, MEDIUM_RISK_MAX_SCORE - 1)

    # Require either strong synchronization or strong
    # inventory pressure before allowing HIGH risk.
    if not (synchronization_strong or inventory_strong):
        return min(weighted_score, MEDIUM_RISK_MAX_SCORE - 1)

    # CRITICAL requires at least three strong signals
    # and strong inventory pressure.
    if strong_signal_count < MIN_SIGNALS_FOR_CRITICAL_RISK:
        return min(weighted_score, HIGH_RISK_MAX_SCORE - 1)

    if not inventory_strong:
        return min(weighted_score, HIGH_RISK_MAX_SCORE - 1)

    return weighted_score

def analyze_collective_risk(events, agents=None):
    """Combine the existing detector outputs into one result per purchase second."""
    velocity_results = analyze_purchase_velocity(events)
    synchronization_results = analyze_purchase_synchronization(events)
    inventory_results = analyze_inventory_impact(events)
    behavior_groups = find_similar_behavior_groups(events, agents)

    velocity_by_window = {result.window_start: result.risk_score for result in velocity_results}
    synchronization_by_window = {
        result.window_start: result.risk_score for result in synchronization_results
    }
    inventory_by_window = {result.window_start: result.risk_score for result in inventory_results}
    behavior_by_agent = build_behavior_scores_by_agent(behavior_groups)
    behavior_by_window = build_behavior_scores_by_window(events, behavior_by_agent)

    results = []
    # Velocity returns exactly the purchase windows, so it provides the timeline.
    for window_start in sorted(velocity_by_window):
        signal_scores = {
            "velocity": velocity_by_window[window_start],
            "synchronization": synchronization_by_window.get(window_start, 0),
            "inventory": inventory_by_window.get(window_start, 0),
            "behavior": behavior_by_window.get(window_start, 0),
        }
        weighted_score = round(
            signal_scores["velocity"] * VELOCITY_WEIGHT
            + signal_scores["synchronization"] * SYNCHRONIZATION_WEIGHT
            + signal_scores["inventory"] * INVENTORY_IMPACT_WEIGHT
            + signal_scores["behavior"] * BEHAVIOR_COORDINATION_WEIGHT
        )
        overall_score = apply_contextual_safeguards(weighted_score, signal_scores)

        results.append(
            CollectiveRiskResult(
                window_start=window_start,
                velocity_score=signal_scores["velocity"],
                synchronization_score=signal_scores["synchronization"],
                inventory_impact_score=signal_scores["inventory"],
                behavior_coordination_score=signal_scores["behavior"],
                overall_risk_score=overall_score,
                overall_risk_level=classify_overall_risk(overall_score),
                reason=build_reason(signal_scores),
            )
        )

    return results


def print_top_results(results, limit=10):
    """Print the highest collective-risk purchase windows."""
    top_results = sorted(
        results,
        key=lambda result: (-result.overall_risk_score, result.window_start),
    )[:limit]

    print("Top 10 potential collective inventory risk windows")
    for result in top_results:
        print(
            f"{result.window_start.isoformat(sep=' ')} | "
            f"velocity={result.velocity_score} | "
            f"synchronization={result.synchronization_score} | "
            f"inventory={result.inventory_impact_score} | "
            f"behavior={result.behavior_coordination_score} | "
            f"overall={result.overall_risk_score} | {result.overall_risk_level}"
        )
    return top_results


def print_highest_result(result):
    """Print a readable explanation for the single highest-risk result."""
    print("\n## AgentShield Collective Risk")
    print(f"Window: {result.window_start.isoformat(sep=' ')}")
    print(f"Velocity: {result.velocity_score}")
    print(f"Synchronization: {result.synchronization_score}")
    print(f"Inventory Impact: {result.inventory_impact_score}")
    print(f"Behavior Coordination: {result.behavior_coordination_score}")
    print(f"Overall Risk: {result.overall_risk_score}")
    print(f"Level: {result.overall_risk_level}")
    print("Main contributing signals:")
    for reason in result.reason.split("; "):
        print(f"- {reason}")
    print("Interpretation: potential collective inventory risk, not proven fraud.")


def run_demo():
    """Compare normal commerce with the controlled inventory-cornering scenario."""

    # ---------------------------------------------------------
    # 1. NORMAL COMMERCE SIMULATION
    # ---------------------------------------------------------
    from simulator.simulator import SupermarketSimulation, create_agents

    print("=" * 70)
    print("NORMAL COMMERCE SCENARIO")
    print("=" * 70)

    normal_agents = create_agents()
    normal_simulation = SupermarketSimulation()
    normal_events = normal_simulation.run(normal_agents)

    normal_results = analyze_collective_risk(
        normal_events,
        normal_agents,
    )

    normal_top = print_top_results(normal_results)

    if normal_top:
        print_highest_result(normal_top[0])

    # ---------------------------------------------------------
    # 2. CONTROLLED ATTACK SCENARIO
    # ---------------------------------------------------------
    from simulator.attack_scenario import run_stress_scenario

    print("\n")
    print("=" * 70)
    print("CONTROLLED INVENTORY CORNERING SCENARIO")
    print("=" * 70)

    attack_events, attack_agents = run_stress_scenario()

    attack_results = analyze_collective_risk(
        attack_events,
        attack_agents,
    )

    attack_top = print_top_results(attack_results)

    if attack_top:
        print_highest_result(attack_top[0])

    # ---------------------------------------------------------
    # 3. SIMPLE COMPARISON
    # ---------------------------------------------------------
    print("\n")
    print("=" * 70)
    print("AGENTSHIELD COMPARISON")
    print("=" * 70)

    if normal_top and attack_top:
        normal_score = normal_top[0].overall_risk_score
        attack_score = attack_top[0].overall_risk_score

        print(f"Normal scenario highest risk : {normal_score}/100")
        print(f"Attack scenario highest risk : {attack_score}/100")

        print("\nAgentShield result:")
        if attack_score > normal_score:
            print("The controlled attack scenario produced a higher collective-risk score.")
        else:
            print("The attack scenario did not produce a higher score in this run.")

    return normal_results, attack_results


if __name__ == "__main__":
    run_demo()
