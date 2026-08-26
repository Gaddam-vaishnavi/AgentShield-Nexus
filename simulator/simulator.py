"""Deterministic supermarket event simulation for AgentShield."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
import random


# A fixed seed makes every run generate the same agents, quantities, and times.
RANDOM_SEED = 20260826
START_TIME = datetime(2026, 8, 26, 9, 0, 0)


@dataclass
class Event:
    """One action taken by an agent while interacting with a product."""

    event_id: str
    agent_id: str
    product_id: str
    action: str
    timestamp: datetime
    quantity: int
    inventory_before: int
    inventory_after: int


class Product:
    """A supermarket product with available inventory."""

    def __init__(self, product_id, name, price, inventory):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.inventory = inventory

    def purchase(self, quantity):
        """Sell all requested units only when enough inventory is available."""
        if quantity > 0 and self.inventory >= quantity:
            self.inventory -= quantity
            return True
        return False

    def reserve(self, quantity):
        """Temporarily remove units from available inventory."""
        return self.purchase(quantity)

    def cancel_reservation(self, quantity):
        """Return reserved units to available inventory."""
        if quantity > 0:
            self.inventory += quantity


class AIBuyerAgent:
    """A buyer agent with an ID, behavior type, and spending budget."""

    def __init__(self, agent_id, behavior_type, budget):
        self.agent_id = agent_id
        self.behavior_type = behavior_type
        self.budget = budget


class SupermarketSimulation:
    """Generates events first, then replays them chronologically for inventory."""

    def __init__(self):
        self.random = random.Random(RANDOM_SEED)
        self.product = Product("P001", "Limited Edition Headphones", 9999, 3000)
        self.starting_inventory = self.product.inventory
        self.events = []
        self.current_time = START_TIME
        self.purchase_attempts = 0
        self.successful_purchases = 0
        self.failed_purchases = 0
        self.successful_purchase_quantity = 0
        self.successful_reservation_quantity = 0
        self.cancelled_reservation_quantity = 0
        self.reservation_for_cancel = {}

    def add_event(self, agent, action, timestamp, quantity=1):
        """Create an event timestamp without changing inventory yet."""
        event = Event(
            event_id=f"E{len(self.events) + 1:06}",
            agent_id=agent.agent_id,
            product_id=self.product.product_id,
            action=action,
            timestamp=timestamp,
            quantity=quantity,
            inventory_before=0,
            inventory_after=0,
        )
        self.events.append(event)
        return event

    def advance_time(self, minimum_seconds, maximum_seconds):
        """Move the event-generation timeline forward by a random time gap."""
        self.current_time += timedelta(
            seconds=self.random.randint(minimum_seconds, maximum_seconds)
        )
        return self.current_time

    def run_purchase_sequence(self, agent, quantity, action_gap_seconds):
        """Generate VIEW, ADD, CHECKOUT, and PURCHASE events for one attempt."""
        self.add_event(agent, "VIEW_PRODUCT", self.advance_time(*action_gap_seconds), quantity)
        self.add_event(agent, "ADD_TO_CART", self.advance_time(*action_gap_seconds), quantity)
        self.add_event(agent, "CHECKOUT", self.advance_time(*action_gap_seconds), quantity)
        self.add_event(agent, "PURCHASE", self.advance_time(*action_gap_seconds), quantity)

    def simulate_normal(self, agent):
        """Normal buyers make one considered purchase attempt for one unit."""
        self.run_purchase_sequence(agent, quantity=1, action_gap_seconds=(30, 240))

    def simulate_fast(self, agent):
        """Fast buyers use the same sequence, but with much shorter time gaps."""
        self.run_purchase_sequence(agent, quantity=1, action_gap_seconds=(1, 8))

    def simulate_aggressive(self, agent):
        """Aggressive buyers make repeated attempts and can request several units."""
        for _ in range(self.random.randint(2, 3)):
            quantity = self.random.randint(1, 3)
            if agent.budget < quantity * self.product.price:
                break
            self.run_purchase_sequence(agent, quantity, action_gap_seconds=(2, 20))

    def simulate_hoarder(self, agent):
        """Hoarders create repeated reservation and cancellation patterns."""
        for _ in range(self.random.randint(2, 4)):
            quantity = self.random.randint(1, 3)
            self.add_event(agent, "VIEW_PRODUCT", self.advance_time(5, 30), quantity)
            reserve_event = self.add_event(
                agent, "RESERVE", self.advance_time(1, 10), quantity
            )
            cancel_event = self.add_event(
                agent, "CANCEL", self.advance_time(10, 90), quantity
            )
            # A cancel returns stock only if this particular reserve succeeds later.
            self.reservation_for_cancel[cancel_event.event_id] = reserve_event.event_id

    def simulate_coordinated_group(self, agents):
        """Give a group nearly identical sequences inside a shared 90-second window."""
        window_start = self.current_time + timedelta(minutes=1)
        for agent in agents:
            event_time = window_start + timedelta(seconds=self.random.randint(0, 90))
            self.add_event(agent, "VIEW_PRODUCT", event_time, 1)
            self.add_event(agent, "ADD_TO_CART", event_time + timedelta(seconds=1), 1)
            self.add_event(agent, "CHECKOUT", event_time + timedelta(seconds=2), 1)
            self.add_event(agent, "PURCHASE", event_time + timedelta(seconds=3), 1)

        self.current_time = window_start + timedelta(seconds=91)

    def process_inventory_timeline(self, agents_by_id):
        """Sort events and replay inventory-changing actions in timestamp order."""
        # Chronological processing is essential for later velocity, timing, and
        # synchronization analysis to use inventory snapshots from the same timeline.
        self.events.sort(key=lambda event: event.timestamp)
        successful_reservations = set()

        for event in self.events:
            event.inventory_before = self.product.inventory

            if event.action == "PURCHASE":
                self.purchase_attempts += 1
                if self.product.purchase(event.quantity):
                    self.successful_purchases += 1
                    self.successful_purchase_quantity += event.quantity
                    agents_by_id[event.agent_id].budget -= event.quantity * self.product.price
                else:
                    self.failed_purchases += 1

            elif event.action == "RESERVE":
                if self.product.reserve(event.quantity):
                    successful_reservations.add(event.event_id)
                    self.successful_reservation_quantity += event.quantity

            elif event.action == "CANCEL":
                reserve_event_id = self.reservation_for_cancel[event.event_id]
                if reserve_event_id in successful_reservations:
                    self.product.cancel_reservation(event.quantity)
                    self.cancelled_reservation_quantity += event.quantity

            # VIEW_PRODUCT, ADD_TO_CART, and CHECKOUT deliberately do not change stock.
            event.inventory_after = self.product.inventory

        self.validate_timeline()

    def validate_timeline(self):
        """Raise a clear error if event order or inventory snapshots are invalid."""
        previous_timestamp = None
        expected_inventory = self.starting_inventory

        for event in self.events:
            if previous_timestamp is not None and event.timestamp < previous_timestamp:
                raise ValueError("Event timeline is not in chronological order.")
            if event.inventory_before != expected_inventory:
                raise ValueError(
                    f"Inventory before {event.event_id} does not match prior inventory state."
                )
            if event.inventory_after < 0:
                raise ValueError(f"Inventory became negative at {event.event_id}.")
            expected_inventory = event.inventory_after
            previous_timestamp = event.timestamp

        if self.product.inventory != expected_inventory:
            raise ValueError("Final product inventory does not match the event timeline.")

        calculated_final_inventory = (
            self.starting_inventory
            - self.successful_purchase_quantity
            - self.successful_reservation_quantity
            + self.cancelled_reservation_quantity
        )
        if self.product.inventory != calculated_final_inventory:
            raise ValueError("Final inventory does not match purchase and reservation totals.")

    def run(self, agents):
        """Generate all events first, then process the sorted event timeline."""
        coordinated_agents = [a for a in agents if a.behavior_type == "coordinated"]
        other_agents = [a for a in agents if a.behavior_type != "coordinated"]
        self.random.shuffle(other_agents)

        self.simulate_coordinated_group(coordinated_agents)
        for agent in other_agents:
            if agent.behavior_type == "normal":
                self.simulate_normal(agent)
            elif agent.behavior_type == "fast":
                self.simulate_fast(agent)
            elif agent.behavior_type == "aggressive":
                self.simulate_aggressive(agent)
            elif agent.behavior_type == "hoarder":
                self.simulate_hoarder(agent)

        self.process_inventory_timeline({agent.agent_id: agent for agent in agents})
        return self.events


def create_agents():
    """Create 5,000 agents with the existing mix of buyer behaviors."""
    agents = []
    behavior_counts = {
        "normal": 2500,
        "fast": 1000,
        "aggressive": 750,
        "hoarder": 500,
        "coordinated": 250,
    }

    for behavior_type, count in behavior_counts.items():
        for number in range(1, count + 1):
            budget = 100_000 if behavior_type == "aggressive" else 20_000
            agent_id = f"{behavior_type[:1].upper()}{number:04}"
            agents.append(AIBuyerAgent(agent_id, behavior_type, budget))

    return agents


def print_event(event):
    """Print one processed event in a compact, readable format."""
    print(
        f"{event.event_id} | {event.timestamp.isoformat(sep=' ')} | "
        f"{event.agent_id} | {event.action} | qty={event.quantity} | "
        f"inventory={event.inventory_before}->{event.inventory_after}"
    )


def run_simulation():
    """Run the full simulation and print the requested event summary."""
    agents = create_agents()
    simulation = SupermarketSimulation()
    events = simulation.run(agents)
    action_counts = Counter(event.action for event in events)
    behavior_counts = Counter(agent.behavior_type for agent in agents)

    print("AgentShield commerce event simulation")
    print(f"Total agents: {len(agents)}")
    print(f"Total events: {len(events)}")
    print(f"Total purchase attempts: {simulation.purchase_attempts}")
    print(f"Successful purchases: {simulation.successful_purchases}")
    print(f"Failed purchases: {simulation.failed_purchases}")
    print(f"Starting inventory: {simulation.starting_inventory}")
    print(f"Final inventory: {simulation.product.inventory}")

    print("\nEvents by action type:")
    for action in ("VIEW_PRODUCT", "ADD_TO_CART", "CHECKOUT", "PURCHASE", "RESERVE", "CANCEL"):
        print(f"  {action}: {action_counts[action]}")

    print("\nAgents by behavior type:")
    for behavior in ("normal", "fast", "aggressive", "hoarder", "coordinated"):
        print(f"  {behavior}: {behavior_counts[behavior]}")

    print("\nFirst 10 chronological events:")
    for event in events[:10]:
        print_event(event)

    return events


if __name__ == "__main__":
    run_simulation()
