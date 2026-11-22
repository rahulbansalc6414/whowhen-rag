"""Labelled queries for the extraction benchmark. Today is fixed at Wednesday 2026-11-18.

Each case: query, expected time ranges, people, sort, list_only.
A role written "created_at|updated_at" accepts either (the wording does not say which).
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
