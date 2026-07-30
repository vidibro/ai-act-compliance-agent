"""Model-call plumbing shared by both layers.

The classification cascade and the gap judge ask a model completely different questions, but they
talk to it the same way: a profile-shaped `litellm.completion`, a JSON reply, a usage tally. That
common part lives here so a provider quirk is fixed once rather than in each layer.

What does NOT belong here: prompts, rubrics, schemas, or anything that knows what a risk class or
an obligation is. This module handles the transport, not the question.
"""

from aiact.llm.json_reply import unfence

__all__ = ["unfence"]
