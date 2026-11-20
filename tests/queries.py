"""Synthetic queries for gate tests and the benchmark. Names and topics are made up."""

# The regex gate must catch these.
REGEX_TIME = [
    "what changed in the refund policy last week?",
    "show me pages updated yesterday",
    "onboarding docs edited this month",
    "release notes from the past 3 days",
    "any new incident reports today?",
    "what's new in the pricing wiki",
    "latest version of the API rate limit doc",
    "most recent sprint retrospective",
    "design reviews since March",
    "meeting notes from Q3",
    "postmortems written in 2025",
    "docs modified after 2026-10-01",
    "roadmap pages created 2 weeks ago",
    "oldest page about the billing service",
    "what did the team decide during last quarter",
    "security policies updated recently",
    "hiring plan changes in the previous 6 months",
    "notes added before Monday",
    "what has changed in the deployment runbook",
    "status updates between January and March",
]

REGEX_AUTHOR = [
    "pages written by Priya",
    "who wrote the incident response playbook?",
    "specs created by Marco about payments",
    "who owns the data retention policy",
    "did Aiko write anything on caching?",
    "has Lena Fischer edited the style guide",
    "docs by Tomas on search ranking",
    "Priya's notes on the vendor review",
    "who is the author of the pricing FAQ",
    "tickets added by Marco",
    "everything authored by the platform team",
    "who updated the SLA document",
]

# The regex gate must let these through as plain questions.
PLAIN = [
    "what is our refund policy?",
    "how do I rotate an API key",
    "explain the billing service architecture",
    "what are the steps in the onboarding checklist",
    "how does search ranking work",
    "what is the data retention period for logs",
    "list the supported payment methods",
    "what does the SLA promise for uptime",
    "how to request access to the analytics dashboard",
    "who is responsible for approving vendor contracts",
    "what is Priya's role on the payments team",
    "what is the escalation path for a sev1 incident",
    "how do we handle chargebacks",
    "what are the caching rules for the CDN",
    "describe the style guide for error messages",
    "what is the difference between staging and production",
    "how many retries does the webhook client make",
    "where is the deployment runbook",
    "what metrics does the health dashboard show",
    "how do we compute monthly active users",
]

# Need a filter, but the wording is outside the regex: this is what the classifier is for.
CLASSIFIER_ONLY = [
    "anything Priya put together on onboarding?",
    "show me Marco's stuff about the billing rewrite",
    "what has been going on with the pricing page these days",
    "pages Aiko touched around the launch",
    "fresh material on the search ranking project",
    "the most up to date runbook for deployments",
    "notes Lena jotted down about the vendor review",
    "how the security policy was reworked over the summer",
]
