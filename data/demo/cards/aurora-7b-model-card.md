# Aurora-7B — model card

**Version / date:** 1.2 — April 2026

## Parties

- **Developed by:** Boreal Research Oy, Espoo, Finland.
- **Placed on the market by:** Boreal Research Oy, Keilaranta 17, 02150 Espoo, Finland. Contact:
  models@boreal-research.example. Made available to downstream providers in the Union through our
  model hub and through two third-party hosting platforms.
- **Deployed by:** not applicable. Aurora-7B is a model, not a system; downstream providers build
  systems on it and take on the provider duties for those systems.
- **This card is written by:** Boreal Research Oy — the provider of the model.

## What is described here

This card describes a general-purpose AI model in the sense of Art. 3(63), and nothing else.
Aurora-7B is a 7-billion-parameter decoder-only transformer language model trained on a broad
corpus of text and code. It displays significant generality: it performs summarisation,
translation between 24 languages, question answering, classification, code completion and
instruction following without task-specific training, and it is designed to be integrated into a
wide variety of downstream systems. No downstream system is described in this card.

## Scope and status

- **Where it is available:** offered to downstream providers in the Union since November 2025.
- **Exclusions claimed:** none.
- **Placed on the market:** version 1.0 in November 2025; version 1.2 in April 2026.

## Systemic risk — Art. 51

- **Cumulative training compute:** 2.1 × 10^24 FLOPs, measured as the sum of floating point
  operations across pre-training and instruction tuning, logged by the training framework. This is
  below the presumption threshold of Art. 51(2).
- **Commission designation or Art. 52(1) notification:** none has been made and none has been
  received as of the date of this card.

## Release terms — Art. 53(2) and 54(6)

Aurora-7B is released under the Apache-2.0 licence, which permits access, use, modification and
distribution without a fee and without a request form. The parameters, including the weights, are
publicly available for download from the model hub. The information on model architecture (layer
count, hidden size, attention layout, tokenizer) and the information on model usage (prompt format,
context length, recommended decoding settings, known limitations) are publicly available in the
repository's documentation. All four limbs hold, so the provider relies on the free and
open-source carve-out of Art. 53(2) and Art. 54(6) for the duties it lifts.

## Training data and copyright — Art. 53(1)(c) and (d)

The training corpus is described in a public training-content summary published on the AI
Office's template. A copyright policy is published alongside it: rights reservations expressed
under Art. 4(3) of Directive (EU) 2019/790 are identified through the robots.txt and TDM
reservation protocol signals and honoured at crawl time and at each refresh of the corpus.

## Evaluation

Reported in the repository: MMLU 68.4, HumanEval 41.2, FLORES-200 average chrF 54.1, TruthfulQA
52.0, toxicity rate on RealToxicityPrompts 2.1%. Red-teaming for prompt injection, jailbreaks and
hazardous-content generation was carried out before release and is summarised in the evaluation
report.

## Out of scope

This card does not describe any AI system. A chatbot, assistant or classifier built on Aurora-7B is
an AI system under Art. 3(66) and is classified by its own intended purpose.
