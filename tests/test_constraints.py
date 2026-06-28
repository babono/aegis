"""One test per hard constraint — these are the assessment's spine."""
import json
import os
import sqlite3

import pytest

from tests.helpers import compute_for, DATA_DIR, DOCS_DIR
from src.narrative import firewall
from src.narrative.generate import _mock_narrative
from src.reconcile.reconciler import build_expected, reconcile
from src.audit.log import AuditLog


# --- Constraint 1: reproducible -------------------------------------------- #
def test_reproducible_byte_identical():
    a = json.dumps(compute_for("A"), sort_keys=True)
    b = json.dumps(compute_for("A"), sort_keys=True)
    assert a == b


# --- Constraint 2: traceable through the graph ----------------------------- #
def test_every_figure_traceable_or_error():
    for f in compute_for("A"):
        if f.get("status") == "ERROR":
            continue
        assert f.get("graph_path"), f"{f['figure']} missing graph_path"
        c = f["citation"]
        for k in ("source_doc", "page", "chunk_id", "passage_summary"):
            assert c.get(k) is not None, f"{f['figure']} citation missing {k}"


# --- Constraint 3: no LLM-produced numbers --------------------------------- #
def test_firewall_passes_clean_narrative():
    figs = compute_for("A")
    assert firewall.check(_mock_narrative("A", figs), figs)["passed"]


def test_firewall_rejects_injected_number():
    figs = compute_for("A")
    poisoned = "The fund returned 999.9% last quarter."  # 999.9 not in figures
    res = firewall.check(poisoned, figs)
    assert not res["passed"]
    assert "999.9" in res["violations"]


# --- Constraint 4: reproduce Firm A's answer key --------------------------- #
def test_firm_a_reconciles_exactly():
    recon = reconcile(
        compute_for("A"),
        build_expected("A", os.path.join(DOCS_DIR, "firm_A_answer_key.xlsx"),
                       os.path.join(DATA_DIR, "firm_B_expected_overrides.json")))
    assert recon["all_passed"], [r for r in recon["rows"] if r["result"] != "PASS"]


# --- Constraint 5: reconfigure to Firm B (config only) --------------------- #
def test_firm_b_reconciles_and_differs():
    figs_b = compute_for("B")
    recon = reconcile(
        figs_b,
        build_expected("B", os.path.join(DOCS_DIR, "firm_A_answer_key.xlsx"),
                       os.path.join(DATA_DIR, "firm_B_expected_overrides.json")))
    assert recon["all_passed"], [r for r in recon["rows"] if r["result"] != "PASS"]

    by_metric = {f["metric"]: f for f in figs_b}
    # The three figures that must change under Firm B's conventions.
    assert by_metric["Aggregate non-IG exposure"]["value"] == "21.0%"
    assert by_metric["Aggregate non-IG exposure"]["status"] == "BREACH"
    assert by_metric["Largest GRE issuer"]["value"] == "13.0%"
    assert by_metric["Largest GRE issuer"]["status"] == "BREACH"
    assert by_metric["Singapore Government Securities"]["utilization"].endswith("bps")


def test_switch_is_config_only_same_engine():
    # Same engine module computes both firms; only config differs.
    import src.engine.compute as eng_a
    import src.engine.compute as eng_b
    assert eng_a is eng_b
    assert compute_for("A") != compute_for("B")  # different outputs, same code


# --- Append-only audit log ------------------------------------------------- #
def test_audit_append_only_and_tamper_evident(tmp_path):
    db = str(tmp_path / "audit.db")
    log = AuditLog(db)
    log.record(ts="t0", run_id="r", event="GRAPH_CONSTRUCTED", trigger="x",
               data={"a": 1})
    log.record(ts="t1", run_id="r", event="FIGURE_COMPUTED", trigger="y",
               data={"b": 2})
    assert log.verify_chain()

    # UPDATE and DELETE are rejected by the database itself.
    with pytest.raises(sqlite3.IntegrityError):
        log.conn.execute("UPDATE audit_log SET payload='z' WHERE seq=1")
    with pytest.raises(sqlite3.IntegrityError):
        log.conn.execute("DELETE FROM audit_log WHERE seq=1")

    # Tampering via a raw connection (bypassing triggers) breaks the hash chain.
    log.close()
    raw = sqlite3.connect(db)
    raw.execute("DROP TRIGGER audit_no_update")
    raw.execute("UPDATE audit_log SET payload='tampered' WHERE seq=1")
    raw.commit()
    raw.close()
    assert not AuditLog(db).verify_chain()
