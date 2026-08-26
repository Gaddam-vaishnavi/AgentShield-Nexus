"""End-to-end AgentShield API demonstration."""

import json
from urllib.request import Request, urlopen

from simulator.attack_scenario import run_stress_scenario


API_URL = "http://127.0.0.1:8000/risk/analyze"


def event_to_json(event):
    """Convert a simulator Event into the API request format."""
    return {
        "event_id": event.event_id,
        "agent_id": event.agent_id,
        "product_id": event.product_id,
        "action": event.action,
        "timestamp": event.timestamp.isoformat(),
        "quantity": event.quantity,
        "inventory_before": event.inventory_before,
        "inventory_after": event.inventory_after,
    }


def main():
    print("=" * 70)
    print("AGENTSHIELD API END-TO-END DEMO")
    print("=" * 70)

    # Generate the existing controlled attack scenario.
    events, agents = run_stress_scenario()

    print("\nSending attack scenario events to AgentShield API...")
    print(f"Events being sent: {len(events)}")

    payload = {
        "events": [event_to_json(event) for event in events]
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

    print("\n" + "=" * 70)
    print("AGENTSHIELD API RESPONSE")
    print("=" * 70)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()