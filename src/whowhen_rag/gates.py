"""Gate 1: a free regex scan for time and author wording.

A hit sends the query straight to extraction. A miss is not a final "no":
the classifier (gate 2) gets a look at it, because people phrase time and
authorship in more ways than any pattern list covers.

False positives are cheap (one extraction call that returns no filter);
false negatives are caught by the classifier. So the patterns lean towards
matching.
"""
from __future__ import annotations

import re

_MONTH = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
_WEEKDAY = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
_UNIT = r"days?|weeks?|weekends?|months?|quarters?|years?|hours?"
_DOC_EVENT = r"updated|modified|changed|edited|created|written|added|published|posted|uploaded|revised"

TIME_PATTERN = re.compile(
    r"\b(?:"
    r"today|yesterday|tonight|lately|recently|recent|latest|newest|oldest|earliest|newly"
    rf"|(?:this|last|past|previous|prior)\s+(?:\d+\s+|few\s+|couple\s+of\s+|several\s+)?(?:{_UNIT})"
    rf"|\d+\s+(?:{_UNIT})\s+ago"
    rf"|(?:since|before|after|until|till|between|during|from)\s+(?:{_MONTH}|{_WEEKDAY}|q[1-4]|(?:19|20)\d{{2}}"
    r"|last|this|yesterday|today)"
    rf"|in\s+(?:{_MONTH}|q[1-4]|(?:19|20)\d{{2}})"
    r"|(?:19|20)\d{2}-\d{1,2}(?:-\d{1,2})?"
    rf"|(?:{_DOC_EVENT})\s+(?:on|in|since|before|after|during|last|this|today|yesterday|recently|lately)"
    r"|what(?:'s|\s+is|\s+has)?\s+(?:new|changed)"
    r")\b",
    re.IGNORECASE,
)

_AUTHOR_VERB = (
    r"wrote|written|write|created|create|authored|author|edited|edit|updated|update|modified|modify"
    r"|changed|change|owns|owned|added|add|posted|post|published|publish|drafted|draft|maintains|maintained"
    r"|uploaded|upload|shared|share"
)
_DOC_NOUN = r"docs?|documents?|pages?|notes?|posts?|articles?|files?|tickets?|specs?|reports?|wikis?|drafts?"

AUTHOR_PATTERN = re.compile(
    r"\b(?:"
    rf"(?:{_AUTHOR_VERB})\s+by"
    rf"|who\s+(?:{_AUTHOR_VERB})"
    rf"|(?:did|has|have|had)\s+(?!to\b)\w+(?:\s+\w+)?\s+(?:{_AUTHOR_VERB})"
    r"|authors?|authored"
    r")\b",
    re.IGNORECASE,
)

# Case-sensitive: a capitalised name next to a document noun ("specs by Priya", "Priya's notes").
NAMED_DOC_PATTERN = re.compile(
    rf"\b(?:(?:{_DOC_NOUN})\s+(?:by|from)\s+[A-Z][a-z]+|[A-Z][a-z]+'s\s+(?:{_DOC_NOUN}))\b"
)


def regex_signal(query: str) -> str | None:
    """Return "time" or "author" if the query has that kind of wording, else None."""
    if TIME_PATTERN.search(query):
        return "time"
    if AUTHOR_PATTERN.search(query) or NAMED_DOC_PATTERN.search(query):
        return "author"
    return None
