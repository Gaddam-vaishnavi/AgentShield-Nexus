from datetime import datetime
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from risk_engine.collective_risk_engine import analyze_collective_risk
from risk_engine.protection_engine import decide_protection
from simulator.simulator import Event
from simulator.attack_scenario import run_stress_scenario


app = FastAPI(title="AgentShield API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class CommerceEvent(BaseModel):
    event_id: str
    agent_id: str
    product_id: str
    action: str
    timestamp: datetime
    quantity: int = 1
    inventory_before: int
    inventory_after: int


class RiskRequest(BaseModel):
    events: List[CommerceEvent]


@app.get("/")
def read_root():
    return {"message": "AgentShield API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/risk/analyze")
def analyze_risk(request: RiskRequest):
    """Analyze commerce events and return an AgentShield risk decision."""

    events = [
        Event(
            event_id=event.event_id,
            agent_id=event.agent_id,
            product_id=event.product_id,
            action=event.action,
            timestamp=event.timestamp,
            quantity=event.quantity,
            inventory_before=event.inventory_before,
            inventory_after=event.inventory_after,
        )
        for event in request.events
    ]

    results = analyze_collective_risk(events)

    if not results:
        return {
            "risk_score": 0,
            "risk_level": "LOW",
            "action": "ALLOW",
            "reason": "No purchase events were available for analysis.",
        }

    highest_risk = max(
        results,
        key=lambda result: result.overall_risk_score,
    )

    decision = decide_protection(
        highest_risk.overall_risk_score
    )

    return {
        "risk_score": highest_risk.overall_risk_score,
        "risk_level": highest_risk.overall_risk_level,
        "action": decision.action,
        "reason": decision.reason,
        "signals": {
            "velocity": highest_risk.velocity_score,
            "synchronization": highest_risk.synchronization_score,
            "inventory_impact": highest_risk.inventory_impact_score,
            "behavior_coordination": highest_risk.behavior_coordination_score,
        },
    }


@app.post("/risk/demo/attack")
def demo_attack_scenario():
    """Run the built-in attack scenario simulation and return an AgentShield
    risk decision for the highest-risk window, using the existing risk
    engine and protection engine (no risk logic is duplicated here)."""

    attack_events, attack_agents = run_stress_scenario()

    results = analyze_collective_risk(attack_events, attack_agents)

    if not results:
        return {
            "risk_score": 0,
            "risk_level": "LOW",
            "action": "ALLOW",
            "reason": "No purchase events were available for analysis.",
            "signals": {
                "velocity": 0,
                "synchronization": 0,
                "inventory_impact": 0,
                "behavior_coordination": 0,
            },
        }

    highest_risk = max(
        results,
        key=lambda result: result.overall_risk_score,
    )

    decision = decide_protection(
        highest_risk.overall_risk_score
    )

    return {
        "risk_score": highest_risk.overall_risk_score,
        "risk_level": highest_risk.overall_risk_level,
        "action": decision.action,
        "reason": decision.reason,
        "signals": {
            "velocity": highest_risk.velocity_score,
            "synchronization": highest_risk.synchronization_score,
            "inventory_impact": highest_risk.inventory_impact_score,
            "behavior_coordination": highest_risk.behavior_coordination_score,
        },
    }