"""End-to-end example with sqlite and an OpenAI-compatible LLM (here: Claude Haiku 5.5 via OpenRouter).

    pip install whowhen-rag openai
    export OPENROUTER_API_KEY=...      # your LLM
    export TYPESAFE_API_KEY=...        # optional: Jev classifier (gate 2)
    python examples/quickstart.py
"""
import os
import sqlite3

from openai import OpenAI

from whowhen_rag import Detector, Field

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])


def llm(prompt: str) -> str:
    response = client.chat.completions.create(
        model="anthropic/claude-haiku-5.5",
        max_tokens=1024,
        extra_body={"reasoning": {"enabled": False}},  # thinking off: faster, cheaper, same answers
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE docs (title TEXT, body TEXT, author_email TEXT, edited_on TEXT)")
db.executemany("INSERT INTO docs VALUES (?, ?, ?, ?)", [
    ("Refund policy", "Refunds within 30 days...", "priya@example.com", "2026-11-12"),
    ("Caching guide", "We cache at the edge...", "marco@example.com", "2026-10-02"),
    ("Onboarding", "Day one checklist...", "priya@example.com", "2026-06-20"),
])

people = {"priya": "priya@example.com", "marco": "marco@example.com"}

detector = Detector(
    fields=[
        Field("edited_on", role="updated_at"),
        Field("author_email", role="created_by", resolve=lambda name: people.get(name.split()[0].lower())),
    ],
    llm=llm,
)

for query in ["what did Priya write recently?", "how does caching work?", "docs edited in October"]:
    f = detector.detect(query)
    where, params = f.to_sql(placeholder="?")
    sql = "SELECT title FROM docs" + (f" WHERE {where}" if where else "")
    if f.recency:  # a hint; here we simply order by the update date (see the README on reranking)
        sql += f" ORDER BY edited_on {'DESC' if f.recency == 'newest' else 'ASC'}"
    rows = [r[0] for r in db.execute(sql, params)]
    print(f"{query!r}\n  gate={f.trace.gate} llm_called={f.trace.llm_called} recency={f.recency}"
          f" search_text={f.cleaned_query!r}\n  {sql} {params}\n  -> {rows}\n")
