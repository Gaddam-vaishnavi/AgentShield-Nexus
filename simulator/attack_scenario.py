"""Controlled inventory-cornering stress scenario for AgentShield testing."""

from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import random


# Load the existing simulator file directly so this script can run from inside
# the simulator folder without Python confusing simulator.py for a package.
SIMULATOR_PATH = Path(__file__).with_name("simulator.py")
simulator_spec = spec_from_file_location("agentshield_simulator", SIMULATOR_PATH)
simulator_module = module_from_spec(simulator_spec)
simulator_spec.loader.exec_module(simulator_module)
AIBuyerAgent = simulator_module.AIBuyerAgent
Event = simulator_module.Event
Product = simulator_module.Product


RANDOM_SEED = 20260826
START_TIME = datetime(2026, 8, 26, 12, 0, 0)
STARTING_INVENTORY = 3000
NUMBER_OF_AGENTS = 500


def add_event(events, agent, product, action, timestamp, quantity):
    """Add a timestamped event before inventory is replayed chronologically."""
    events.append(
        Event(
            event_id=f"S{len(events) + 1:06}",
            agent_id=agent.agent_id,
            product_id=product.product_id,
            action=action,
            timestamp=timestamp,
            quantity=quantity,
            inventory_before=0,
            inventory_after=0,
        )
    )


def create_scenario_events(product, agents, randomizer):
    """Create nearly identical shopping sequences inside a three-second window."""
    events = []
    for agent in agents:
        # Each request is within the required 3-8 unit range. Using 6-8 units
        # intentionally creates high collective pressure against 3,000 units.
        quantity = randomizer.randint(6, 8)
        # Millisecond-level variation prevents events from being exactly identical.
        start_offset_ms = randomizer.randint(0, 2_000)
        first_action_time = START_TIME + timedelta(milliseconds=start_offset_ms)

        add_event(events, agent, product, "VIEW_PRODUCT", first_action_time, quantity)
        add_event(
            events,
            agent,
            product,
            "ADD_TO_CART",
            first_action_time + timedelta(milliseconds=randomizer.randint(50, 100)),
            quantity,
        )
        add_event(
            events,
            agent,
            product,
            "CHECKOUT",
            first_action_time + timedelta(milliseconds=randomizer.randint(110, 170)),
            quantity,
        )
        add_event(
            events,
            agent,
            product,
            "PURCHASE",
            first_action_time + timedelta(milliseconds=randomizer.randint(180, 260)),
            quantity,
        )

    return events


def process_events_chronologically(events, product):
    """Replay purchases in time order, recording accurate inventory snapshots."""
    events.sort(key=lambda event: event.timestamp)
    summary = {
        "purchase_attempts": 0,
        "requested_quantity": 0,
        "successful_quantity": 0,
        "failed_quantity": 0,
    }

    for event in events:
        event.inventory_before = product.inventory
        if event.action == "PURCHASE":
            summary["purchase_attempts"] += 1
            summary["requested_quantity"] += event.quantity
            if product.purchase(event.quantity):
                summary["successful_quantity"] += event.quantity
            else:
                # Failed requests never consume inventory.
                summary["failed_quantity"] += event.quantity
        event.inventory_after = product.inventory

        if event.inventory_after < 0:
            raise ValueError("Inventory became negative in the stress scenario.")

    return summary


def print_event(event):
    """Print an event with millisecond timestamps for easy timeline inspection."""
    timestamp = event.timestamp.isoformat(sep=" ", timespec="milliseconds")
    print(
        f"{event.event_id} | {timestamp} | {event.agent_id} | {event.action} | "
        f"qty={event.quantity} | inventory={event.inventory_before}->{event.inventory_after}"
    )


def run_stress_scenario():
    """Run and report the Controlled Inventory Cornering Stress Scenario."""
    randomizer = random.Random(RANDOM_SEED)
    product = Product("P001", "Limited Edition Headphones", 9999, STARTING_INVENTORY)
    agents = [
        AIBuyerAgent(f"C{number:04}", "coordinated", 100_000)
        for number in range(1, NUMBER_OF_AGENTS + 1)
    ]
    events = create_scenario_events(product, agents, randomizer)
    summary = process_events_chronologically(events, product)

    print("Controlled Inventory Cornering Stress Scenario")
    print(f"Starting inventory: {STARTING_INVENTORY}")
    print(f"Number of agents: {len(agents)}")
    print(f"Purchase attempts: {summary['purchase_attempts']}")
    print(f"Total requested quantity: {summary['requested_quantity']}")
    print(f"Successful quantity: {summary['successful_quantity']}")
    print(f"Failed quantity: {summary['failed_quantity']}")
    print(f"Final inventory: {product.inventory}")
    print(f"Total events: {len(events)}")

    print("\nFirst 20 chronological events:")
    for event in events[:20]:
        print_event(event)

    return events, agents


if __name__ == "__main__":
    run_stress_scenario()
