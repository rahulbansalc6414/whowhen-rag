"""whowhen-rag: detect time and author filters in RAG queries, cheaply.

    from whowhen_rag import Detector, Field

    detector = Detector(
        fields=[Field("modified_on", role="updated_at"), Field("owner", role="created_by")],
        llm=my_llm,  # prompt in, text out
    )
    filters = detector.detect("what did Priya change last week?")
"""
from importlib.metadata import PackageNotFoundError, version

from .classifier import Classifier, JevClassifier
from .detector import Detector
from .fields import Field
from .filters import Condition, Filters, Sort, Trace
from .gates import regex_signal

__all__ = [
    "Classifier",
    "Condition",
    "Detector",
    "Field",
    "Filters",
    "JevClassifier",
    "Sort",
    "Trace",
    "regex_signal",
]
try:
    __version__ = version("whowhen-rag")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0"
