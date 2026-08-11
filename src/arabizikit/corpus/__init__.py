"""Corpus collection and evaluation tooling for arabizikit (v0.2).

The pipeline harvests real Arabizi from public sources, filters it down to
high-confidence Arabizi sentences, annotates them with an LLM (Arabic script
plus dialect tag), and splits the result into a stratified held-out set that
``arabizikit eval --data <test.json>`` can score.
"""
