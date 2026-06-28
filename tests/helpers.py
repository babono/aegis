"""Shared test helpers — build a client + compute figures for a firm."""
import json
import os

from src.config.loader import load_config
from src.engine.compute import compute_all
from src.graph.client import make_client
from src.ingest.extract_holdings import load_positions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "sample_docs")


def load_graph():
    with open(os.path.join(DATA_DIR, "extracted_graph.json"), encoding="utf-8") as fh:
        return json.load(fh)


def compute_for(firm: str):
    cfg = load_config(firm, CONFIG_DIR)
    graph = load_graph()
    positions = load_positions(os.path.join(DOCS_DIR, "sample_holdings.csv"))
    client = make_client("embedded")
    client.load(graph, positions)
    chunks = {c["chunk_id"]: c for c in graph["chunks"]}
    return compute_all(client, cfg, chunks)
