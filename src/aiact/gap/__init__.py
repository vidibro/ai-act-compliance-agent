"""Gap analysis: judge a provider's documentation against the obligations that apply to it.

Layer two of two, and the counterpart to `aiact.classify`. It takes that layer's output as an
argument rather than importing it: neither layer depends on the other, and what they genuinely
share sits outside both — model-call plumbing (`aiact.llm`), provider profiles, usage, tracing, the
question-anchoring in `aiact.anchoring`, and the brain contract in `aiact.brain`.

WHOSE the obligations are is decided here, not by the cascade. Every question the cascade asks
decides what the SYSTEM is and yields a risk class; Art. 25 decides who the READER is, consuming
that class and changing nothing about it. So the role logic lives together: which duties a class
activates (rules.py) and who ends up holding them (roles.py).

Module layout:
    roles.py   Art. 25 — has the provider's role changed hands? One question, high-risk only.
    rules.py   which obligations a classified use case activates — pure data, no model.
    judge.py   one bounded question per rule, against retrieved evidence.
    graph.py   the LangGraph tying those together into a ComplianceReport.
"""
