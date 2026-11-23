"""The labelled question set for benchmarks/run.py. Today is fixed at Wednesday 2026-11-18.

Each case: (query, expected time ranges, people, sort, list_only).
- An empty case (no ranges, no people, no sort) means the query needs no filter.
- "a|b" accepts either value: roles ("created_at|updated_at"), dates ("2026-03-01|2026-04-01",
  "open" for no end) and names ("platform team|the platform team").
- ALTERNATIVES lists queries where two different answers are both acceptable.

Groups record when each set was written, so held-out scores stay visible:
main (with prompt v1), holdout (before v2), fresh (after v2 was final), fresh2 (before v3),
gates (the regex/classifier set, labelled 2026-11-22 before the first single-benchmark run).
"""

TODAY = "2026-11-18"

CASES = [
    # time only
    ("what changed in the refund policy last week?", [("updated_at", "2026-11-09", "2026-11-16")], [], None, False),
    ("pages updated yesterday", [("updated_at", "2026-11-17", "2026-11-18")], [], None, True),
    ("onboarding docs edited this month", [("updated_at", "2026-11-01", None)], [], None, False),
    ("postmortems written in 2025", [("created_at", "2025-01-01", "2026-01-01")], [], None, False),
    ("design reviews created since March", [("created_at", "2026-03-01", None)], [], None, False),
    ("docs modified in October", [("updated_at", "2026-10-01", "2026-11-01")], [], None, True),
    ("meeting notes created in Q3", [("created_at", "2026-07-01", "2026-10-01")], [], None, False),
    ("security policies updated in the last 30 days", [("updated_at", "2026-10-19", None)], [], None, False),
    ("notes edited before September", [("updated_at", None, "2026-09-01")], [], None, False),
    ("list documents created last month", [("created_at", "2026-10-01", "2026-11-01")], [], None, True),
    # sort only
    ("latest deployment runbook", [], [], ("created_at|updated_at", "newest"), False),
    ("oldest page about the billing service", [], [], ("created_at|updated_at", "oldest"), False),
    # people only
    ("pages written by Priya", [], [("created_by", "Priya")], None, True),
    ("specs created by Marco about payments", [], [("created_by", "Marco")], None, False),
    ("did Aiko write anything on caching?", [], [("created_by", "Aiko")], None, False),
    ("has Lena Fischer edited the style guide", [], [("updated_by", "Lena Fischer")], None, False),
    ("docs by Tomas on search ranking", [], [("created_by", "Tomas")], None, False),
    ("Priya's notes on the vendor review", [], [("created_by", "Priya")], None, False),
    ("anything Priya put together on onboarding?", [], [("created_by", "Priya")], None, False),
    ("show me Marco's stuff about the billing rewrite", [], [("created_by", "Marco")], None, False),
    ("pages written by Priya or Marco", [], [("created_by", "Priya"), ("created_by", "Marco")], None, True),
    # combined
    ("pricing docs Priya edited last week", [("updated_at", "2026-11-09", "2026-11-16")],
     [("updated_by", "Priya")], None, False),
    ("pages Priya created this week", [("created_at", "2026-11-16", None)], [("created_by", "Priya")], None, True),
    ("what did Marco change in the API docs yesterday", [("updated_at", "2026-11-17", "2026-11-18")],
     [("updated_by", "Marco")], None, False),
    ("most recent docs by Aiko", [], [("created_by", "Aiko")], ("created_at|updated_at", "newest"), True),
    # no filter (the LLM must not invent one)
    ("what is our refund policy?", [], [], None, False),
    ("what is Priya's role on the payments team", [], [], None, False),
    ("how does the 2025 pricing model work", [], [], None, False),
    ("who is responsible for approving vendor contracts", [], [], None, False),
    ("who wrote the incident response playbook?", [], [], None, False),
]

# Held out: written before the prompt-v2 changes, never used to tune the prompt.
HOLDOUT = [
    ("tickets updated over the past two weeks", [("updated_at", "2026-11-04", None)], [], None, True),
    ("contracts drafted by Marco in 2024", [("created_at", "2024-01-01", "2025-01-01")],
     [("created_by", "Marco")], None, False),
    ("notes edited today", [("updated_at", "2026-11-18", None)], [], None, True),
    ("the newest onboarding checklist", [], [], ("created_at|updated_at", "newest"), False),
    ("which docs did Lena Fischer update this month", [("updated_at", "2026-11-01", None)],
     [("updated_by", "Lena Fischer")], None, True),
    ("explain the Q4 planning process", [], [], None, False),
    ("summary of the 2026 hiring plan", [], [], None, False),
    ("how do I submit an expense report", [], [], None, False),
    ("pages created between June and August", [("created_at", "2026-06-01", "2026-09-01")], [], None, True),
    ("runbooks Aiko changed last month", [("updated_at", "2026-10-01", "2026-11-01")],
     [("updated_by", "Aiko")], None, False),
    ("anything new on the search project since Monday", [("created_at|updated_at", "2026-11-16", None)],
     [], None, False),
    ("who approved the travel policy", [], [], None, False),
    ("specs written by Tomas or Priya about billing", [], [("created_by", "Tomas"), ("created_by", "Priya")],
     None, False),
    ("design docs created in May", [("created_at", "2026-05-01", "2026-06-01")], [], None, False),
    ("what did the security team write in March 2025", [("created_at", "2025-03-01", "2025-04-01")], [], None, False),
]

# Fresh: written 2026-11-22 after prompt v2 was final, labelled before the first run.
# Not used to tune any prompt. The clean held-out measurement for v2.
FRESH = [
    ("architecture notes Marco wrote in August", [("created_at", "2026-08-01", "2026-09-01")],
     [("created_by", "Marco")], None, False),
    ("show everything edited yesterday", [("updated_at", "2026-11-17", "2026-11-18")], [], None, True),
    ("pages created this year about compliance", [("created_at", "2026-01-01", None)], [], None, False),
    ("what did Aiko update last week in the onboarding guide", [("updated_at", "2026-11-09", "2026-11-16")],
     [("updated_by", "Aiko")], None, False),
    ("who maintains the release checklist", [], [], None, False),
    ("the 2024 security audit findings", [], [], None, False),
    ("how does Q2 revenue recognition work", [], [], None, False),
    ("the oldest notes on the data migration", [], [], ("created_at|updated_at", "oldest"), False),
    ("docs Lena Fischer created in 2025", [("created_at", "2025-01-01", "2026-01-01")],
     [("created_by", "Lena Fischer")], None, True),
    ("postmortems from the last 90 days", [("created_at|updated_at", "2026-08-20", None)], [], None, False),
    ("what changed in the vendor policy since September", [("updated_at", "2026-09-01", None)], [], None, False),
    ("pages written by Tomas before June", [("created_at", None, "2026-06-01")], [("created_by", "Tomas")],
     None, True),
    ("what is Marco's opinion on the caching proposal", [], [], None, False),
    ("the latest pricing FAQ", [], [], ("created_at|updated_at", "newest"), False),
    ("notes edited in the past 48 hours", [("updated_at", "2026-11-16", None)], [], None, True),
]

# Fresh 2: written 2026-11-22 before prompt v3 existed, labelled before any run.
# The clean measurement for v3 (and a second clean one for v2).
FRESH2 = [
    ("what was added to the API guide since August", [("updated_at", "2026-08-01", None)], [], None, False),
    ("reports created before March", [("created_at", None, "2026-03-01")], [], None, True),
    ("pages created since January", [("created_at", "2026-01-01", None)], [], None, True),
    ("what is Lena's view on remote work", [], [], None, False),
    ("what does Tomas think about the new pricing", [], [], None, False),
    ("design docs updated since December", [("updated_at", "2025-12-01", None)], [], None, False),
    ("incident notes created in December", [("created_at", "2025-12-01", "2026-01-01")], [], None, False),
    ("specs Marco edited since the start of October", [("updated_at", "2026-10-01", None)],
     [("updated_by", "Marco")], None, False),
    ("pages created last year", [("created_at", "2025-01-01", "2026-01-01")], [], None, True),
    ("who leads the payments team", [], [], None, False),
    ("notes from 2023 about the data warehouse", [("created_at|updated_at", "2023-01-01", "2024-01-01")], [],
     None, False),
    ("the most recent compliance checklist", [], [], ("created_at|updated_at", "newest"), False),
    ("Priya's latest draft of the launch plan", [], [("created_by", "Priya")], ("created_at|updated_at", "newest"),
     False),
    ("how did the 2023 migration go", [], [], None, False),
    ("what has Marco written since April", [("created_at", "2026-04-01", None)], [("created_by", "Marco")], None, True),
]


# Gate-set questions not already above. Labelled 2026-11-22 before any single-benchmark run.
GATES = [
    # time wording
    ("show me pages updated yesterday", [("updated_at", "2026-11-17", "2026-11-18")], [], None, True),
    ("release notes from the past 3 days", [("created_at|updated_at", "2026-11-15", "open|2026-11-19")], [], None,
     False),
    ("any new incident reports today?", [("created_at|updated_at", "2026-11-18", "open|2026-11-19")], [], None,
     False),
    ("what's new in the pricing wiki", [], [], ("created_at|updated_at", "newest"), False),
    ("latest version of the API rate limit doc", [], [], ("created_at|updated_at", "newest"), False),
    ("most recent sprint retrospective", [], [], ("created_at|updated_at", "newest"), False),
    ("design reviews since March", [("created_at|updated_at", "2026-03-01", None)], [], None, False),
    ("meeting notes from Q3", [("created_at|updated_at", "2026-07-01", "2026-10-01")], [], None, False),
    ("docs modified after 2026-10-01", [("updated_at", "2026-10-01|2026-10-02", None)], [], None, True),
    ("roadmap pages created 2 weeks ago",
     [("created_at", "2026-11-02|2026-11-04", "open|2026-11-05|2026-11-09|2026-11-11")], [], None, False),
    ("what did the team decide during last quarter", [("created_at|updated_at", "2026-07-01", "2026-10-01")], [],
     None, False),
    ("security policies updated recently", [], [], ("updated_at", "newest"), False),
    ("hiring plan changes in the previous 6 months", [("updated_at|created_at", "2026-05-18", None)], [], None,
     False),
    ("notes added before Monday", [("created_at", None, "2026-11-16")], [], None, True),
    ("what has changed in the deployment runbook", [], [], ("updated_at", "newest"), False),
    ("status updates between January and March",
     [("created_at|updated_at", "2026-01-01", "2026-03-01|2026-04-01")], [], None, False),
    # author wording
    ("who owns the data retention policy", [], [], None, False),
    ("who is the author of the pricing FAQ", [], [], None, False),
    ("tickets added by Marco", [], [("created_by", "Marco")], None, True),
    ("everything authored by the platform team", [], [("created_by", "platform team|the platform team")], None,
     True),
    ("who updated the SLA document", [], [], None, False),
    # unusual wording (what the classifier is for)
    ("what has been going on with the pricing page these days", [], [], ("created_at|updated_at", "newest"), False),
    ("pages Aiko touched around the launch", [], [("updated_by|created_by", "Aiko")], None, False),
    ("fresh material on the search ranking project", [], [], ("created_at|updated_at", "newest"), False),
    ("the most up to date runbook for deployments", [], [], ("created_at|updated_at", "newest"), False),
    ("notes Lena jotted down about the vendor review", [], [("created_by", "Lena")], None, False),
    ("how the security policy was reworked over the summer",
     [("updated_at|created_at", "2026-06-01|2026-06-21", "2026-09-01|2026-09-22|2026-09-23")], [], None, False),
    # plain
    ("how do I rotate an API key", [], [], None, False),
    ("explain the billing service architecture", [], [], None, False),
    ("what are the steps in the onboarding checklist", [], [], None, False),
    ("how does search ranking work", [], [], None, False),
    ("what is the data retention period for logs", [], [], None, False),
    ("list the supported payment methods", [], [], None, False),
    ("what does the SLA promise for uptime", [], [], None, False),
    ("how to request access to the analytics dashboard", [], [], None, False),
    ("what is the escalation path for a sev1 incident", [], [], None, False),
    ("how do we handle chargebacks", [], [], None, False),
    ("what are the caching rules for the CDN", [], [], None, False),
    ("describe the style guide for error messages", [], [], None, False),
    ("what is the difference between staging and production", [], [], None, False),
    ("how many retries does the webhook client make", [], [], None, False),
    ("where is the deployment runbook", [], [], None, False),
    ("what metrics does the health dashboard show", [], [], None, False),
    ("how do we compute monthly active users", [], [], None, False),
]

# Queries where a second, different answer is also acceptable.
ALTERNATIVES = {
    # "what has changed" with no period: a recency sort or no filter are both reasonable.
    "what has changed in the deployment runbook": [([], [], None, False)],
}

GROUPS = {"main": CASES, "holdout": HOLDOUT, "fresh": FRESH, "fresh2": FRESH2, "gates": GATES}
ALL = [(group, case) for group, cases in GROUPS.items() for case in cases]
