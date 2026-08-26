"""AgentShield decision and inventory-protection engine."""

from dataclasses import dataclass


# Risk thresholds.
MONITOR_MAX_SCORE = 49
CHALLENGE_MAX_SCORE = 74


@dataclass
class ProtectionDecision:
    """Represents the action AgentShield recommends."""

    risk_score: int
    risk_level: str
    action: str
    reason: str


def decide_protection(risk_score):
    """
    Convert a collective risk score into a protection decision.

    The engine does not directly block payments.
    It returns a recommendation for the commerce layer.
    """

    if risk_score < 25:
        return ProtectionDecision(
            risk_score=risk_score,
            risk_level="LOW",
            action="ALLOW",
            reason="Low collective risk. Continue normal commerce.",
        )

    if risk_score <= MONITOR_MAX_SCORE:
        return ProtectionDecision(
            risk_score=risk_score,
            risk_level="MEDIUM",
            action="MONITOR",
            reason=(
                "Moderate collective risk. Continue the transaction "
                "while monitoring the agent behavior."
            ),
        )

    if risk_score <= CHALLENGE_MAX_SCORE:
        return ProtectionDecision(
            risk_score=risk_score,
            risk_level="HIGH",
            action="CHALLENGE",
            reason=(
                "High collective risk. Add verification or rate limiting "
                "before allowing continued automated purchasing."
            ),
        )

    return ProtectionDecision(
        risk_score=risk_score,
        risk_level="CRITICAL",
        action="PROTECT_INVENTORY",
        reason=(
            "Critical collective inventory risk. Apply inventory "
            "protection and prevent one coordinated group from "
            "exhausting scarce stock."
        ),
    )


def print_decision(decision):
    """Print a readable AgentShield protection decision."""

    print("\n" + "=" * 60)
    print("AGENTSHIELD PROTECTION DECISION")
    print("=" * 60)

    print(f"Risk score : {decision.risk_score}/100")
    print(f"Risk level : {decision.risk_level}")
    print(f"Action     : {decision.action}")
    print(f"Reason     : {decision.reason}")


def run_demo():
    """Demonstrate the four protection levels."""

    test_scores = [15, 40, 65, 95]

    print("AgentShield Protection Engine Demo")

    for score in test_scores:
        decision = decide_protection(score)
        print_decision(decision)


if __name__ == "__main__":
    run_demo()