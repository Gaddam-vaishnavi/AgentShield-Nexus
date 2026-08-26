"""Fourth AgentShield risk signal: observed behavior similarity and coordination."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys


# These prototype settings are intentionally easy to tune later.
SIMILARITY_THRESHOLD = 85
MIN_GROUP_SIZE = 5
SHARED_TIME_BUCKET_MINUTES = 5

# Purchase-time spans use these windows to measure precise alignment.
TIGHT_PURCHASE_SPAN_SECONDS = 90
MODERATE_PURCHASE_SPAN_SECONDS = 180
WIDE_PURCHASE_SPAN_SECONDS = 300
MIN_ALIGNMENT_FOR_HIGH_RISK = 60
MIN_ALIGNMENT_FOR_CRITICAL_RISK = 80


@dataclass
class BehaviorProfile:
    """The observed event pattern for one agent."""

    agent_id: str
    behavior_type: str | None
    action_sequence: tuple[str, ...]
    purchase_attempts: int
    total_requested_quantity: int
    average_time_gap_seconds: float
    first_event_time: datetime
    purchase_timestamps: tuple[datetime, ...]


@dataclass
class BehaviorGroup:
    """A group whose members have closely matching observed profiles."""

    group_id: str
    number_of_agents: int
    agent_ids: list[str]
    average_similarity: float
    common_action_sequence: tuple[str, ...]
    average_purchase_attempts: float
    average_requested_quantity: float
    purchase_time_span_seconds: float
    timing_alignment_score: int
    average_purchase_time_gap_seconds: float
    coordination_score: int
    risk_level: str


def extract_behavior_profiles(events, agents=None):
    """Build one profile per agent from chronological simulator events.

    behavior_type is attached only when an agent list is supplied for validation
    or explanation. It is never used by the grouping or similarity logic.
    """
    behavior_types = {}
    if agents is not None:
        behavior_types = {agent.agent_id: agent.behavior_type for agent in agents}

    events_by_agent = defaultdict(list)
    for event in sorted(events, key=lambda item: item.timestamp):
        events_by_agent[event.agent_id].append(event)

    profiles = []
    for agent_id, agent_events in events_by_agent.items():
        action_sequence = tuple(event.action for event in agent_events)
        purchase_events = [event for event in agent_events if event.action == "PURCHASE"]
        total_requested_quantity = sum(event.quantity for event in purchase_events)

        time_gaps = [
            (agent_events[index].timestamp - agent_events[index - 1].timestamp).total_seconds()
            for index in range(1, len(agent_events))
        ]
        average_gap = sum(time_gaps) / len(time_gaps) if time_gaps else 0.0

        profiles.append(
            BehaviorProfile(
                agent_id=agent_id,
                behavior_type=behavior_types.get(agent_id),
                action_sequence=action_sequence,
                purchase_attempts=len(purchase_events),
                total_requested_quantity=total_requested_quantity,
                average_time_gap_seconds=round(average_gap, 2),
                first_event_time=agent_events[0].timestamp,
                purchase_timestamps=tuple(event.timestamp for event in purchase_events),
            )
        )

    return profiles


def calculate_similarity(first, second):
    """Compare two profiles transparently and return a score from 0 to 100.

    Action sequence is 40% of the score. Purchase attempts, requested quantity,
    and average timing gap contribute 20% each.
    """
    longest_sequence = max(len(first.action_sequence), len(second.action_sequence), 1)
    matching_actions = sum(
        first_action == second_action
        for first_action, second_action in zip(first.action_sequence, second.action_sequence)
    )
    sequence_similarity = matching_actions / longest_sequence

    attempt_similarity = 1 - abs(
        first.purchase_attempts - second.purchase_attempts
    ) / max(first.purchase_attempts, second.purchase_attempts, 1)
    quantity_similarity = 1 - abs(
        first.total_requested_quantity - second.total_requested_quantity
    ) / max(first.total_requested_quantity, second.total_requested_quantity, 1)
    timing_similarity = 1 - min(
        abs(first.average_time_gap_seconds - second.average_time_gap_seconds)
        / max(first.average_time_gap_seconds, second.average_time_gap_seconds, 1),
        1,
    )

    return round(
        (
            sequence_similarity * 0.4
            + attempt_similarity * 0.2
            + quantity_similarity * 0.2
            + timing_similarity * 0.2
        )
        * 100,
        2,
    )


def shared_time_bucket(timestamp):
    """Place timestamps into a coarse shared-time bucket without agent labels."""
    bucket_minute = timestamp.minute - (timestamp.minute % SHARED_TIME_BUCKET_MINUTES)
    return timestamp.replace(minute=bucket_minute, second=0, microsecond=0)


def candidate_key(profile):
    """Create an efficient observed-behavior bucket key for candidate groups."""
    return (
        profile.action_sequence,
        profile.purchase_attempts,
        profile.total_requested_quantity,
        round(profile.average_time_gap_seconds),
        shared_time_bucket(profile.first_event_time),
    )


def classify_risk(coordination_score):
    """Convert a coordination score to a readable risk level."""
    if coordination_score < 25:
        return "LOW"
    if coordination_score < 50:
        return "MEDIUM"
    if coordination_score < 75:
        return "HIGH"
    return "CRITICAL"


def calculate_timing_alignment_score(purchase_time_span_seconds):
    """Score the spread of a group's PURCHASE timestamps from 0 to 100.

    A span of 90 seconds or less receives 100. The score gradually drops to 60
    at 180 seconds, to 20 at 300 seconds, and to 0 beyond that. The values are
    intentionally configurable because acceptable timing differs by product.
    """
    if purchase_time_span_seconds <= TIGHT_PURCHASE_SPAN_SECONDS:
        return 100
    if purchase_time_span_seconds <= MODERATE_PURCHASE_SPAN_SECONDS:
        proportion = (
            purchase_time_span_seconds - TIGHT_PURCHASE_SPAN_SECONDS
        ) / (MODERATE_PURCHASE_SPAN_SECONDS - TIGHT_PURCHASE_SPAN_SECONDS)
        return round(100 - proportion * 40)
    if purchase_time_span_seconds <= WIDE_PURCHASE_SPAN_SECONDS:
        proportion = (
            purchase_time_span_seconds - MODERATE_PURCHASE_SPAN_SECONDS
        ) / (WIDE_PURCHASE_SPAN_SECONDS - MODERATE_PURCHASE_SPAN_SECONDS)
        return round(60 - proportion * 40)
    return 0


def calculate_purchase_timing_details(members):
    """Return the purchase span, alignment score, and average gap for a group."""
    purchase_times = sorted(
        timestamp for member in members for timestamp in member.purchase_timestamps
    )
    if not purchase_times:
        return 0.0, 0, 0.0

    purchase_time_span = (purchase_times[-1] - purchase_times[0]).total_seconds()
    purchase_gaps = [
        (purchase_times[index] - purchase_times[index - 1]).total_seconds()
        for index in range(1, len(purchase_times))
    ]
    average_purchase_gap = sum(purchase_gaps) / len(purchase_gaps) if purchase_gaps else 0.0
    return (
        round(purchase_time_span, 2),
        calculate_timing_alignment_score(purchase_time_span),
        round(average_purchase_gap, 2),
    )


def calculate_coordination_score(average_similarity, timing_alignment_score, group_size):
    """Combine profile similarity, precise alignment, and group size transparently.

    average_similarity already contains action sequence, purchase-attempt count,
    requested quantity, and per-agent timing-gap similarity. Precise alignment
    contributes 40%, while group size contributes up to 10 additional points.
    """
    group_size_points = min(10, max(0, group_size - MIN_GROUP_SIZE))
    coordination_score = round(
        average_similarity * 0.5 + timing_alignment_score * 0.4 + group_size_points
    )

    # Similar sequences without tight purchase timing cannot become high/critical.
    if timing_alignment_score < MIN_ALIGNMENT_FOR_HIGH_RISK:
        return min(49, coordination_score)
    if timing_alignment_score < MIN_ALIGNMENT_FOR_CRITICAL_RISK:
        return min(74, coordination_score)
    return min(100, coordination_score)


def find_similar_behavior_groups(events, agents=None):
    """Find high-similarity groups without comparing all 5,000 agents pairwise.

    Profiles are first placed in exact observed-behavior buckets. Only members
    of the same small candidate bucket are compared to one representative.
    This avoids unnecessary O(n^2) work across the whole population.
    """
    candidate_groups = defaultdict(list)
    for profile in extract_behavior_profiles(events, agents):
        candidate_groups[candidate_key(profile)].append(profile)

    detected_groups = []
    for candidates in candidate_groups.values():
        if len(candidates) < MIN_GROUP_SIZE:
            continue

        representative = candidates[0]
        members = [representative]
        similarities = []
        for candidate in candidates[1:]:
            similarity = calculate_similarity(representative, candidate)
            if similarity >= SIMILARITY_THRESHOLD:
                members.append(candidate)
                similarities.append(similarity)

        if len(members) < MIN_GROUP_SIZE:
            continue

        # The representative has an implicit 100% similarity with itself.
        average_similarity = round(
            (100 + sum(similarities)) / len(members), 2
        )
        (
            purchase_time_span_seconds,
            timing_alignment_score,
            average_purchase_time_gap_seconds,
        ) = calculate_purchase_timing_details(members)
        coordination_score = calculate_coordination_score(
            average_similarity, timing_alignment_score, len(members)
        )
        common_sequence = Counter(member.action_sequence for member in members).most_common(1)[0][0]

        detected_groups.append(
            BehaviorGroup(
                group_id=f"BG{len(detected_groups) + 1:03}",
                number_of_agents=len(members),
                agent_ids=[member.agent_id for member in members],
                average_similarity=average_similarity,
                common_action_sequence=common_sequence,
                average_purchase_attempts=round(
                    sum(member.purchase_attempts for member in members) / len(members), 2
                ),
                average_requested_quantity=round(
                    sum(member.total_requested_quantity for member in members) / len(members), 2
                ),
                purchase_time_span_seconds=purchase_time_span_seconds,
                timing_alignment_score=timing_alignment_score,
                average_purchase_time_gap_seconds=average_purchase_time_gap_seconds,
                coordination_score=coordination_score,
                risk_level=classify_risk(coordination_score),
            )
        )

    return sorted(
        detected_groups,
        key=lambda group: (-group.coordination_score, -group.number_of_agents),
    )


def print_top_groups(groups, limit=10):
    """Print the highest-scoring behavior groups in a compact format."""
    print("Top 10 highest-similarity behavior groups")
    for group in groups[:limit]:
        agent_preview = ", ".join(group.agent_ids[:10])
        if group.number_of_agents > 10:
            agent_preview += ", ..."
        print(
            f"{group.group_id} | agents={group.number_of_agents} | "
            f"similarity={group.average_similarity} | "
            f"attempts_avg={group.average_purchase_attempts} | "
            f"requested_avg={group.average_requested_quantity} | "
            f"purchase_span={group.purchase_time_span_seconds}s | "
            f"timing_alignment={group.timing_alignment_score} | "
            f"purchase_gap_avg={group.average_purchase_time_gap_seconds}s | "
            f"coordination={group.coordination_score} | {group.risk_level}\n"
            f"  sequence={' -> '.join(group.common_action_sequence)}\n"
            f"  agent_ids={agent_preview}"
        )


def run_demo():
    """Run the existing simulator and print high-similarity observed groups."""
    repository_root = Path(__file__).resolve().parents[1]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    from simulator.simulator import SupermarketSimulation, create_agents

    agents = create_agents()
    simulation = SupermarketSimulation()
    events = simulation.run(agents)
    groups = find_similar_behavior_groups(events, agents)
    print_top_groups(groups)
    print("\nHigher scores require both similar behavior and tightly aligned purchase times.")
    print("\nBehavior similarity is a risk signal, not proof of malicious coordination.")
    return groups


if __name__ == "__main__":
    run_demo()
