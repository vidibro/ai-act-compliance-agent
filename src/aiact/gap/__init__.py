"""Gap analysis: judge a provider's documentation against the obligations that apply to it.

Layer two of two, and the counterpart to `aiact.classify`. It takes that layer's output as an
argument rather than importing it: neither layer depends on the other, and what they genuinely
share — model-call plumbing (`aiact.llm`), provider profiles, usage, tracing — sits outside both.

Module layout:
    rules.py   which obligations a classified use case activates — pure data, no model.
    judge.py   one bounded question per rule, against retrieved evidence.
    graph.py   the LangGraph tying those together into a ComplianceReport.
"""
