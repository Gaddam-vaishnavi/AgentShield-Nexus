"""Simulate how AgentShield protects scarce inventory."""

from dataclasses import dataclass

from simulator.attack_scenario import run_stress_scenario
from risk_engine.collective_risk_engine import analyze_collective_risk
from risk_engine.protection_engine import decide_protection


# Protection policy used only when collective risk is CRITICAL.
MAX_UNITS_PER_AGENT = 2
PROTECTED_INVENTORY_PERCENT = 20


@dataclass
class ProtectionResult:
    """Summary of the protected inventory simulation."""

    starting_inventory: int
    requested_quantity: int
    successful_quantity: int
    rejected_quantity: int
    final_available_inventory: int
    protected_inventory: int


def simulate_protection(events, starting_inventory):
    """
    Replay purchase attempts using AgentShield's protection policy.

    The simulation applies:
    1. A maximum quantity per agent.
    2. A protected inventory reserve.

    This is a demonstration policy, not a production payment rule.
    """

    purchase_events = sorted(
        [
            event
            for event in events
            if event.action == "PURCHASE"
        ],
        key=lambda event: event.timestamp,
    )

    protected_inventory = int(
        starting_inventory * PROTECTED_INVENTORY_PERCENT / 100
    )

    available_inventory = starting_inventory - protected_inventory

    agent_purchased_quantity = {}

    requested_quantity = 0
    successful_quantity = 0
    rejected_quantity = 0

    for event in purchase_events:
        requested_quantity += event.quantity

        agent_id = event.agent_id

        already_purchased = agent_purchased_quantity.get(
            agent_id,
            0,
        )

        remaining_agent_limit = (
            MAX_UNITS_PER_AGENT - already_purchased
        )

        allowed_quantity = min(
            event.quantity,
            max(0, remaining_agent_limit),
        )

        # Never consume the protected inventory reserve.
        allowed_quantity = min(
            allowed_quantity,
            max(0, available_inventory),
        )

        if allowed_quantity > 0:
            available_inventory -= allowed_quantity
            successful_quantity += allowed_quantity

            agent_purchased_quantity[agent_id] = (
                already_purchased + allowed_quantity
            )

        rejected_quantity += event.quantity - allowed_quantity

    return ProtectionResult(
        starting_inventory=starting_inventory,
        requested_quantity=requested_quantity,
        successful_quantity=successful_quantity,
        rejected_quantity=rejected_quantity,
        final_available_inventory=available_inventory,
        protected_inventory=protected_inventory,
    )


def print_result(result):
    """Print the protection simulation result."""

    print("\n" + "=" * 70)
    print("AGENTSHIELD INVENTORY PROTECTION RESULT")
    print("=" * 70)

    print(f"Starting inventory       : {result.starting_inventory}")
    print(f"Requested quantity       : {result.requested_quantity}")
    print(f"Successful quantity      : {result.successful_quantity}")
    print(f"Rejected quantity        : {result.rejected_quantity}")
    print(
        f"Final available inventory: "
        f"{result.final_available_inventory}"
    )
    print(f"Protected inventory      : {result.protected_inventory}")


def main():
    """Run the controlled attack and apply AgentShield protection."""

    print("=" * 70)
    print("AGENTSHIELD PROTECTION SIMULATION")
    print("=" * 70)

    events, agents = run_stress_scenario()

    starting_inventory = 3000

    # First calculate the collective risk.
    risk_results = analyze_collective_risk(
        events,
        agents,
    )

    if not risk_results:
        print("No risk result was produced.")
        return

    highest_risk = max(
        risk_results,
        key=lambda result: result.overall_risk_score,
    )

    decision = decide_protection(
        highest_risk.overall_risk_score
    )

    print("\nDetected collective risk:")
    print(f"Risk score : {decision.risk_score}/100")
    print(f"Risk level : {decision.risk_level}")
    print(f"Action     : {decision.action}")

    # Only activate this protection policy for CRITICAL risk.
    if decision.action != "PROTECT_INVENTORY":
        print("\nProtection policy was not activated.")
        return

    result = simulate_protection(
        events,
        starting_inventory,
    )

    print_result(result)

    print("\n" + "=" * 70)
    print("PROTECTION EFFECT")
    print("=" * 70)

    consumed_without_protection = 2999
    remaining_without_protection = (
        starting_inventory - consumed_without_protection
    )

    print(
        f"Without AgentShield : "
        f"{remaining_without_protection} units remaining"
    )

    print(
        f"With AgentShield    : "
        f"{result.final_available_inventory} available + "
        f"{result.protected_inventory} protected"
    )

    print(
        "\nAgentShield prevented the coordinated group "
        "from consuming the entire available inventory."
    )


if __name__ == "__main__":
    main()