"""LLM-assisted extraction of the guidelines into a candidate graph.

IMPORTANT — read this in the context of constraint 3 (the LLM may not be the
source of any reported number):

  * This module runs ONLY when a human explicitly re-extracts
    (`python run.py --re-extract`). Its output is a *candidate* that MUST pass
    the human review gate (src/review/gate.py) before anything trusts it.
  * The committed data/extracted_graph.json is the already-approved artifact.
    Normal runs read that frozen file and never call this module — which is why
    figures reproduce byte-for-byte with no API key.
  * Even here, the LLM only proposes STRUCTURE (which limits/thresholds exist).
    The numeric limits it extracts are checked by a human against the source
    passages at the gate. The LLM is never in the path that COMPUTES a reported
    figure — that is the deterministic engine, downstream of the approved graph.

If the openai SDK or a key is unavailable, this raises a clear error telling the
user to use the committed extraction instead.
"""
from __future__ import annotations

import json
import os
from typing import Any

EXTRACTION_PROMPT = """You are extracting a knowledge graph from an asset-management
guidelines document. Return STRICT JSON with keys: chunks, nodes, edges.
Extract asset classes and their allocation limits (min/max % of NAV), the
aggregate non-IG cap, single-issuer and GRE concentration caps, the liquidity
floor, and risk metrics with their thresholds, breach actions and owners.
Every node and edge MUST carry provenance {source_doc, page, chunk_id,
ingested_at, extraction_confidence}. Do NOT compute any portfolio figure; only
extract limits and structure stated verbatim in the document.
Document text follows:
---
%s
---
Return ONLY the JSON object."""


def _read_pdf_text(pdf_path: str) -> str:
    import pdfplumber  # imported lazily; only needed for re-extraction

    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            parts.append(f"[page {i}]\n{page.extract_text() or ''}")
    return "\n\n".join(parts)


def reextract(pdf_path: str, model: str = "deepseek-chat") -> dict[str, Any]:
    """Produce a CANDIDATE extraction via DeepSeek. Must go through the gate."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Re-extraction needs DEEPSEEK_API_KEY. For normal runs you do not "
            "need it — the committed, human-approved data/extracted_graph.json "
            "is used and every figure reproduces without any LLM."
        )
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    text = _read_pdf_text(pdf_path)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT % text}],
        temperature=0,  # extraction is not creative; keep it as stable as possible
        response_format={"type": "json_object"},
    )
    candidate = json.loads(resp.choices[0].message.content)
    candidate.setdefault("meta", {})["extraction_method"] = "llm_candidate_unapproved"
    return candidate
