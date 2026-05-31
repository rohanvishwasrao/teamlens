import json
from datetime import datetime


def load_jira():
    with open("mock_data/jira_mock.json") as f:
        return json.load(f)


def load_pagerduty():
    with open("mock_data/pagerduty_mock.json") as f:
        return json.load(f)


# ── Metric 1: Sprint Velocity ─────────────────────────────────
# Tracks committed vs completed story points per sprint.
# Declining completion rate = team is overloaded or blocked.

def compute_sprint_velocity(jira_data):
    """
    Returns list of sprints with committed vs completed points.
    This powers the velocity trend chart.
    """
    results = []
    for sprint in jira_data["sprints"]:
        results.append({
            "sprint": sprint["name"].split("—")[0].strip(),  # "Sprint 41"
            "committed": sprint["velocity_points_committed"],
            "completed": sprint["velocity_points_completed"],
            "completion_pct": round(
                sprint["velocity_points_completed"] /
                sprint["velocity_points_committed"] * 100, 1
            ),
            "carry_over": sprint["velocity_points_committed"] - sprint["velocity_points_completed"]
        })
    return results


# ── Metric 2: Cycle Time per Engineer ────────────────────────
# How long does each engineer's tickets take to resolve?
# High cycle time = blocked, overloaded, or scope issues.

def compute_cycle_time_by_engineer(jira_data):
    """
    Returns average cycle time in days per engineer.
    Only counts resolved tickets (cycle_time_days is not null).
    """
    engineer_times = {}  # login → list of cycle times

    for sprint in jira_data["sprints"]:
        for ticket in sprint["tickets"]:
            if ticket["cycle_time_days"] is None:
                continue
            assignee = ticket["assignee"]
            if assignee not in engineer_times:
                engineer_times[assignee] = []
            engineer_times[assignee].append(ticket["cycle_time_days"])

    results = []
    for engineer, times in engineer_times.items():
        results.append({
            "engineer": engineer,
            "avg_cycle_time_days": round(sum(times) / len(times), 1),
            "tickets_resolved": len(times),
            "max_cycle_time_days": max(times)
        })

    # Sort by avg cycle time descending — longest first
    return sorted(results, key=lambda x: x["avg_cycle_time_days"], reverse=True)


# ── Metric 3: Oncall Burden ───────────────────────────────────
# Who is getting paged the most? After-hours pages are weighted
# higher because they directly impact sleep and personal time.

def compute_oncall_burden(pd_data):
    """
    Returns oncall burden score per engineer.
    Score = total_incidents + (2 * after_hours_incidents)
    After-hours weighted 2x because of personal time impact.
    """
    burden = pd_data["oncall_burden_summary"]["incidents_by_engineer"]

    results = []
    for engineer, stats in burden.items():
        after_hours = stats["after_hours_pages"]
        total = stats["total_incidents"]
        p0_p1 = stats["p0_p1_incidents"]

        # Weighted burden score
        score = total + (2 * after_hours) + (3 * p0_p1)

        results.append({
            "engineer": engineer,
            "total_incidents": total,
            "after_hours_pages": after_hours,
            "p0_p1_incidents": p0_p1,
            "avg_ack_time_minutes": stats["avg_ack_time_minutes"],
            "burden_score": score,
            "risk_level": "High" if score >= 10 else "Medium" if score >= 5 else "Low"
        })

    return sorted(results, key=lambda x: x["burden_score"], reverse=True)


# ── Metric 4: Blocked Ticket Analysis ────────────────────────
# How many days of blocked work per engineer?
# Chronic blocking = external dependency problems or unclear ownership.

def compute_blocked_work(jira_data):
    """
    Returns total blocked days per engineer across all tickets.
    """
    blocked = {}

    for sprint in jira_data["sprints"]:
        for ticket in sprint["tickets"]:
            if ticket["blocked_days"] > 0:
                assignee = ticket["assignee"]
                if assignee not in blocked:
                    blocked[assignee] = {
                        "engineer": assignee,
                        "total_blocked_days": 0,
                        "blocked_tickets": [],
                    }
                blocked[assignee]["total_blocked_days"] += ticket["blocked_days"]
                blocked[assignee]["blocked_tickets"].append({
                    "ticket": ticket["id"],
                    "days": ticket["blocked_days"],
                    "reason": ticket["blocker_reason"]
                })

    return sorted(
        blocked.values(),
        key=lambda x: x["total_blocked_days"],
        reverse=True
    )


# ── Metric 5: Burnout Risk Score ─────────────────────────────
# Composite score combining oncall burden, blocked work,
# carry-over tickets, and review load.
# This is the headline metric of TeamLens.

def compute_burnout_risk(jira_data, pd_data):
    """
    Composite burnout risk per engineer — pulls from all sources.

    Factors:
    - Oncall burden score (from PagerDuty)
    - Total blocked days (from Jira)
    - Carry-over tickets (from Jira)
    - Unresolved tickets (from Jira)

    Returns risk level: High / Medium / Low
    """
    oncall = {e["engineer"]: e for e in compute_oncall_burden(pd_data)}
    blocked = {e["engineer"]: e for e in compute_blocked_work(jira_data)}

    # Count carry-overs and unresolved per engineer
    carry_overs = {}
    unresolved = {}
    for sprint in jira_data["sprints"]:
        for ticket in sprint["tickets"]:
            a = ticket["assignee"]
            if ticket["status"] in ["Carried over", "In Progress", "To Do"]:
                carry_overs[a] = carry_overs.get(a, 0) + 1
            if ticket["status"] != "Done":
                unresolved[a] = unresolved.get(a, 0) + 1

    # All engineers across all sources
    all_engineers = set(
        list(oncall.keys()) +
        list(blocked.keys()) +
        list(carry_overs.keys())
    )

    results = []
    for engineer in all_engineers:
        oncall_score = oncall.get(engineer, {}).get("burden_score", 0)
        blocked_days = blocked.get(engineer, {}).get("total_blocked_days", 0)
        carry_over_count = carry_overs.get(engineer, 0)
        unresolved_count = unresolved.get(engineer, 0)

        # Composite score — weighted combination
        score = (
            oncall_score * 2 +       # oncall is highest signal
            blocked_days * 1.5 +     # blocking is demoralizing
            carry_over_count * 2 +   # carry-overs indicate overload
            unresolved_count * 1     # general workload
        )

        results.append({
            "engineer": engineer,
            "burnout_score": round(score, 1),
            "risk_level": "🔴 High" if score >= 20 else "🟡 Medium" if score >= 10 else "🟢 Low",
            "oncall_burden": oncall_score,
            "blocked_days": blocked_days,
            "carry_overs": carry_over_count,
            "unresolved_tickets": unresolved_count
        })

    return sorted(results, key=lambda x: x["burnout_score"], reverse=True)


# ── Metric 6: Incident Trend ──────────────────────────────────
# Incidents grouped by month — shows if reliability is improving.

def compute_incident_trend(pd_data):
    """
    Groups incidents by month and severity.
    Powers the reliability trend chart.
    """
    monthly = {}

    for incident in pd_data["incidents"]:
        # Parse month from created_at — "2024-01-09T02:14:00Z" → "2024-01"
        month = incident["created_at"][:7]
        if month not in monthly:
            monthly[month] = {"month": month, "total": 0, "p0_p1": 0, "p2": 0}
        monthly[month]["total"] += 1
        if incident["severity"] in ["P0", "P1"]:
            monthly[month]["p0_p1"] += 1
        else:
            monthly[month]["p2"] += 1

    return sorted(monthly.values(), key=lambda x: x["month"])


# ── All metrics in one call ───────────────────────────────────

def compute_all_metrics(prs=None):
    """
    Master function — computes all metrics and returns as a dict.
    Called once at app startup and cached.
    """
    jira = load_jira()
    pd_data = load_pagerduty()

    return {
        "sprint_velocity": compute_sprint_velocity(jira),
        "cycle_time_by_engineer": compute_cycle_time_by_engineer(jira),
        "oncall_burden": compute_oncall_burden(pd_data),
        "blocked_work": compute_blocked_work(jira),
        "burnout_risk": compute_burnout_risk(jira, pd_data),
        "incident_trend": compute_incident_trend(pd_data),
    }


# ── Test it ───────────────────────────────────────────────────
if __name__ == "__main__":

    metrics = compute_all_metrics()

    print("\n── Sprint Velocity ──────────────────────────────")
    for s in metrics["sprint_velocity"]:
        print(f"  {s['sprint']}: {s['completed']}/{s['committed']} pts ({s['completion_pct']}%)")

    print("\n── Cycle Time by Engineer ───────────────────────")
    for e in metrics["cycle_time_by_engineer"]:
        print(f"  {e['engineer']:<20} avg {e['avg_cycle_time_days']} days ({e['tickets_resolved']} tickets)")

    print("\n── Oncall Burden ────────────────────────────────")
    for e in metrics["oncall_burden"]:
        print(f"  {e['engineer']:<20} score={e['burden_score']} | after-hours={e['after_hours_pages']} | {e['risk_level']}")

    print("\n── Blocked Work ─────────────────────────────────")
    for e in metrics["blocked_work"]:
        print(f"  {e['engineer']:<20} {e['total_blocked_days']} blocked days")

    print("\n── 🔥 Burnout Risk ──────────────────────────────")
    for e in metrics["burnout_risk"]:
        print(f"  {e['engineer']:<20} score={e['burnout_score']} {e['risk_level']}")

    print("\n── Incident Trend ───────────────────────────────")
    for m in metrics["incident_trend"]:
        print(f"  {m['month']}: {m['total']} incidents ({m['p0_p1']} P0/P1)")