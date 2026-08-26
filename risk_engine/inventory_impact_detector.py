"""Third AgentShield risk signal: inventory impact per one-second window."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys


# These percentages use original product inventory, not the stock left later.
# They can be tuned as the product catalog grows.
LOW_MAX_PRESSURE_PERCENT = 0.25
MEDIUM_MAX_PRESSURE_PERCENT = 0.75
HIGH_MAX_PRESSURE_PERCENT = 2.0
MAX_SINGLE_UNIT_SCORE = 19


@dataclass
class InventoryImpactResult:
    """Purchase demand and actual inventory consumption for one second."""

    window_start: datetime
    inventory_before: int
    purchase_attempts: int
    unique_agents: int
    requested_quantity: int
    successful_quantity: int
    failed_quantity: int
    remaining_inventory: int
    consumption_percent_of_starting_inventory: float
    requested_percent_of_starting_inventory: float
    risk_score: int
    risk_level: str


def calculate_risk_score(requested_percent, consumption_percent):
    """Convert collective inventory pressure into a gradual 0-100 score.

    The score blends 60% requested pressure with 40% actual consumption. It uses
    original starting inventory as the denominator, so late-stage depletion does
    not inflate the score. Inventory impact alone does not prove malicious behavior.
    """
    pressure_percent = requested_percent * 0.6 + consumption_percent * 0.4

    if pressure_percent <= LOW_MAX_PRESSURE_PERCENT:
        return round(pressure_percent / LOW_MAX_PRESSURE_PERCENT * 20)
    if pressure_percent <= MEDIUM_MAX_PRESSURE_PERCENT:
        return round(
            20
            + (pressure_percent - LOW_MAX_PRESSURE_PERCENT)
            / (MEDIUM_MAX_PRESSURE_PERCENT - LOW_MAX_PRESSURE_PERCENT)
            * 25
        )
    if pressure_percent <= HIGH_MAX_PRESSURE_PERCENT:
        return round(
            45
            + (pressure_percent - MEDIUM_MAX_PRESSURE_PERCENT)
            / (HIGH_MAX_PRESSURE_PERCENT - MEDIUM_MAX_PRESSURE_PERCENT)
            * 29
        )
    return min(100, round(75 + (pressure_percent - HIGH_MAX_PRESSURE_PERCENT) * 10))


def classify_risk(risk_score):
    """Convert the numeric score to a readable risk level."""
    if risk_score < 20:
        return "LOW"
    if risk_score < 45:
        return "MEDIUM"
    if risk_score < 75:
        return "HIGH"
    return "CRITICAL"


def analyze_inventory_impact(events):
    """Return inventory impact for windows containing PURCHASE events.

    Events are sorted again defensively. Original starting inventory is captured
    separately from the first chronological event. The first event in each window
    supplies inventory_before, and the last supplies remaining_inventory.
    """
    windows = defaultdict(
        lambda: {
            "inventory_before": None,
            "remaining_inventory": None,
            "purchase_attempts": 0,
            "agents": set(),
            "requested_quantity": 0,
            "successful_quantity": 0,
            "failed_quantity": 0,
        }
    )

    chronological_events = sorted(events, key=lambda item: item.timestamp)
    if not chronological_events:
        return []

    # This stays constant across all windows, unlike inventory_before.
    starting_inventory = chronological_events[0].inventory_before

    for event in chronological_events:
        window_start = event.timestamp.replace(microsecond=0)
        window = windows[window_start]

        # These snapshots come from the simulator's already-replayed timeline.
        if window["inventory_before"] is None:
            window["inventory_before"] = event.inventory_before
        window["remaining_inventory"] = event.inventory_after

        if event.action != "PURCHASE":
            continue

        window["purchase_attempts"] += 1
        window["agents"].add(event.agent_id)
        window["requested_quantity"] += event.quantity

        # A successful purchase reduces inventory. Use the actual reduction,
        # rather than the request size, so failed requests never count as consumed.
        consumed_quantity = event.inventory_before - event.inventory_after
        if consumed_quantity > 0:
            window["successful_quantity"] += consumed_quantity
            window["failed_quantity"] += event.quantity - consumed_quantity
        else:
            window["failed_quantity"] += event.quantity

    results = []
    for window_start in sorted(windows):
        window = windows[window_start]
        if window["purchase_attempts"] == 0:
            continue

        if starting_inventory > 0:
            consumption_percent = (
                window["successful_quantity"] / starting_inventory * 100
            )
            requested_percent = (
                window["requested_quantity"] / starting_inventory * 100
            )
        else:
            consumption_percent = 0.0
            requested_percent = 0.0

        risk_score = calculate_risk_score(requested_percent, consumption_percent)
        # One person buying one unit is not collective critical pressure, even
        # if it happens to be the final item in stock.
        if (
            len(window["agents"]) == 1
            and window["requested_quantity"] == 1
            and window["successful_quantity"] <= 1
        ):
            risk_score = min(risk_score, MAX_SINGLE_UNIT_SCORE)
        results.append(
            InventoryImpactResult(
                window_start=window_start,
                inventory_before=window["inventory_before"],
                purchase_attempts=window["purchase_attempts"],
                unique_agents=len(window["agents"]),
                requested_quantity=window["requested_quantity"],
                successful_quantity=window["successful_quantity"],
                failed_quantity=window["failed_quantity"],
                remaining_inventory=window["remaining_inventory"],
                consumption_percent_of_starting_inventory=round(consumption_percent, 2),
                requested_percent_of_starting_inventory=round(requested_percent, 2),
                risk_score=risk_score,
                risk_level=classify_risk(risk_score),
            )
        )

    return results


def print_top_windows(results, limit=10):
    """Print windows with the largest requested share of original inventory."""
    top_windows = sorted(
        results,
        key=lambda result: (
            -result.requested_percent_of_starting_inventory,
            -result.consumption_percent_of_starting_inventory,
            result.window_start,
        ),
    )[:limit]

    print("Top 10 highest-inventory-impact purchase windows")
    for result in top_windows:
        print(
            f"{result.window_start.isoformat(sep=' ')} | "
            f"inventory_before={result.inventory_before} | "
            f"attempts={result.purchase_attempts} | "
            f"unique_agents={result.unique_agents} | "
            f"requested={result.requested_quantity} | "
            f"successful={result.successful_quantity} | "
            f"failed={result.failed_quantity} | "
            f"remaining={result.remaining_inventory} | "
            f"requested%={result.requested_percent_of_starting_inventory:.2f}% | "
            f"consumed%={result.consumption_percent_of_starting_inventory:.2f}% | "
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
    results = analyze_inventory_impact(events)
    print_top_windows(results)
    print("\nInventory impact is one risk signal and does not by itself prove malicious behavior.")
    return results


if __name__ == "__main__":
    run_demo()
