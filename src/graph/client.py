"""Knowledge-graph access layer.

Two interchangeable backends behind one interface:

  * Neo4jClient   — the headline backend (docker compose). Stores the graph in
    Neo4j and answers every figure's inputs with a real Cypher traversal.
  * EmbeddedClient — a pure-Python graph over the same nodes/edges so the system
    also runs with `pip install && python run.py` (no container) and so tests
    need no external service.

Both expose the SAME high-level "view" methods and return IDENTICAL structures.
Figure inputs (positions, limits, memberships) are always obtained by traversing
the graph — the engine never reads the source documents directly. The Cypher-
style graph_path strings emitted with each figure are built by the engine from
the entities these traversals return, so they are backend-independent and
faithful to constraint 2 (figure -> graph path -> source).
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional

from src.util import D


# --------------------------------------------------------------------------- #
# Embedded (pure-Python) backend                                              #
# --------------------------------------------------------------------------- #
class EmbeddedClient:
    backend = "embedded"

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.positions: list[dict] = []
        self._by_label: dict[str, list[str]] = {}

    # ---- build ---------------------------------------------------------- #
    def load(self, graph: dict[str, Any], positions: list[dict]) -> dict:
        self.nodes, self.edges, self.positions = {}, [], []
        self._by_label = {}
        for n in graph["nodes"]:
            self.nodes[n["id"]] = n
            for label in n["labels"]:
                self._by_label.setdefault(label, []).append(n["id"])
        self.edges = list(graph["edges"])
        self.positions = sorted(positions, key=lambda p: p["instrument_id"])
        return {"nodes": len(self.nodes), "edges": len(self.edges),
                "positions": len(self.positions)}

    # ---- internal helpers ---------------------------------------------- #
    def _node_by_prop(self, label: str, prop: str, value: Any) -> Optional[dict]:
        for nid in self._by_label.get(label, []):
            if self.nodes[nid]["props"].get(prop) == value:
                return self.nodes[nid]
        return None

    def _out(self, node_id: str, etype: str) -> list[tuple[dict, dict]]:
        """Outgoing (target_node, edge) pairs of a given type, sorted by target id."""
        res = [(self.nodes[e["to"]], e) for e in self.edges
               if e["from"] == node_id and e["type"] == etype]
        return sorted(res, key=lambda t: t[0]["id"])

    def _in(self, node_id: str, etype: str) -> list[tuple[dict, dict]]:
        res = [(self.nodes[e["from"]], e) for e in self.edges
               if e["to"] == node_id and e["type"] == etype]
        return sorted(res, key=lambda t: t[0]["id"])

    # ---- views (shared contract) --------------------------------------- #
    def total_nav(self) -> Decimal:
        return sum((D(p["market_value_sgd"]) for p in self.positions), Decimal(0))

    def asset_class_view(self, name: str) -> dict:
        ac = self._node_by_prop("AssetClass", "name", name)
        if ac is None:
            raise KeyError(f"AssetClass not in graph: {name}")
        limits = self._out(ac["id"], "HAS_LIMIT")
        if not limits:
            raise KeyError(f"AssetClass {name} has no HAS_LIMIT edge")
        lim, _ = limits[0]
        positions = [p for p in self.positions if p["asset_class"] == name]
        return {
            "code": ac["props"]["code"],
            "name": name,
            "limit": dict(lim["props"]),
            "provenance": lim["provenance"],
            "positions": positions,
        }

    def non_ig_view(self) -> dict:
        agg = self._node_by_prop("Aggregate", "name", "non_ig")
        contributors = self._in(agg["id"], "CONTRIBUTES_TO")
        classes = [{"code": n["props"]["code"], "name": n["props"]["name"]}
                   for n, _ in contributors]
        classes.sort(key=lambda c: c["code"])
        lim, _ = self._out(agg["id"], "HAS_LIMIT")[0]
        return {
            "aggregate_code": agg["props"]["name"],
            "contributing_classes": classes,
            "limit": dict(lim["props"]),
            "provenance": lim["provenance"],
        }

    def cap_view(self, name: str) -> dict:
        cap = self._node_by_prop("Cap", "name", name)
        if cap is None:
            raise KeyError(f"Cap not in graph: {name}")
        return {"code": cap["props"]["name"], "limit": dict(cap["props"]),
                "provenance": cap["provenance"]}

    def floor_view(self, name: str) -> dict:
        fl = self._node_by_prop("Floor", "name", name)
        if fl is None:
            raise KeyError(f"Floor not in graph: {name}")
        return {"code": fl["props"]["name"], "limit": dict(fl["props"]),
                "provenance": fl["provenance"]}

    def risk_metric_view(self, name: str) -> dict:
        rm = self._node_by_prop("RiskMetric", "name", name)
        if rm is None:
            raise KeyError(f"RiskMetric not in graph: {name}")
        thr, _ = self._out(rm["id"], "HAS_THRESHOLD")[0]
        ba_edges = self._out(rm["id"], "HAS_BREACH_ACTION")
        breach = owner = None
        if ba_edges:
            ba, _ = ba_edges[0]
            breach = dict(ba["props"])
            own_edges = self._out(ba["id"], "OWNED_BY")
            if own_edges:
                owner = dict(own_edges[0][0]["props"])
        return {
            "code": rm["props"]["name"],
            "label": rm["props"].get("label"),
            "threshold": dict(thr["props"]),
            "breach_action": breach,
            "owner": owner,
            "provenance": thr["provenance"],
        }

    def issuer_exposures(self, issuer_type: str, group_by: str) -> list[dict]:
        """Aggregate position market values by issuer or by parent issuer.

        Traverses (Position)-[:ISSUED_BY]->(Issuer)[-[:ROLLS_UP_TO]->(Parent)].
        group_by: 'issuer' | 'parent_issuer'.
        """
        buckets: dict[str, dict] = {}
        for p in self.positions:
            if p["issuer_type"] != issuer_type:
                continue
            if group_by == "parent_issuer":
                key = p["parent_issuer"] or p["issuer_name"]
            else:
                key = p["issuer_name"]
            b = buckets.setdefault(key, {"key": key, "market_value": Decimal(0),
                                         "instruments": [], "issuers": set()})
            b["market_value"] += D(p["market_value_sgd"])
            b["instruments"].append(p["instrument_id"])
            b["issuers"].add(p["issuer_name"])
        out = []
        for b in buckets.values():
            out.append({"key": b["key"], "market_value": b["market_value"],
                        "instruments": sorted(b["instruments"]),
                        "issuers": sorted(b["issuers"])})
        # Deterministic: largest first, then key for ties.
        out.sort(key=lambda x: (-x["market_value"], x["key"]))
        return out

    def all_positions(self) -> list[dict]:
        return list(self.positions)

    def close(self) -> None:
        pass


# --------------------------------------------------------------------------- #
# Neo4j backend                                                               #
# --------------------------------------------------------------------------- #
class Neo4jClient:
    backend = "neo4j"

    def __init__(self, uri: str, user: str, password: str, retries: int = 30) -> None:
        import time

        from neo4j import GraphDatabase
        from neo4j.exceptions import ServiceUnavailable, AuthError

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        # Tolerate the docker-compose startup race: Neo4j may accept HTTP (the
        # healthcheck) slightly before Bolt is ready for queries.
        last_exc = None
        for _ in range(retries):
            try:
                self.driver.verify_connectivity()
                return
            except (ServiceUnavailable, AuthError, OSError) as exc:
                last_exc = exc
                time.sleep(2)
        raise RuntimeError(f"Neo4j not reachable at {uri}: {last_exc}")

    def load(self, graph: dict[str, Any], positions: list[dict]) -> dict:
        with self.driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
            # Nodes: primary label + :Entity, provenance stored as JSON string.
            for n in sorted(graph["nodes"], key=lambda x: x["id"]):
                label = n["labels"][0]
                s.run(
                    f"CREATE (x:`{label}`:Entity {{id:$id}}) "
                    "SET x += $props, x.provenance=$prov",
                    id=n["id"], props=n["props"],
                    prov=json.dumps(n["provenance"], sort_keys=True),
                )
            for e in sorted(graph["edges"], key=lambda x: (x["from"], x["to"], x["type"])):
                s.run(
                    f"MATCH (a:Entity {{id:$f}}),(b:Entity {{id:$t}}) "
                    f"CREATE (a)-[r:`{e['type']}`]->(b) SET r.provenance=$prov",
                    f=e["from"], t=e["to"],
                    prov=json.dumps(e["provenance"], sort_keys=True),
                )
            # Positions + issuer / parent rollup.
            for p in sorted(positions, key=lambda x: x["instrument_id"]):
                s.run(
                    "MATCH (ac:AssetClass {name:$ac}) "
                    "CREATE (pos:Position:Entity {id:$iid}) SET pos += $props, "
                    "pos.provenance=$prov "
                    "MERGE (iss:Issuer:Entity {id:$issid}) "
                    "  ON CREATE SET iss.name=$issuer, iss.issuer_type=$itype "
                    "CREATE (pos)-[:IN_ASSET_CLASS]->(ac) "
                    "CREATE (pos)-[:ISSUED_BY]->(iss)",
                    ac=p["asset_class"], iid=p["instrument_id"],
                    issid="iss_" + p["issuer_name"].lower().replace(" ", "_"),
                    issuer=p["issuer_name"], itype=p["issuer_type"],
                    props={k: v for k, v in p.items() if k != "provenance"},
                    prov=json.dumps(p["provenance"], sort_keys=True),
                )
                if p["parent_issuer"]:
                    s.run(
                        "MATCH (iss:Issuer {id:$issid}) "
                        "MERGE (par:Issuer:Entity {id:$parid}) "
                        "  ON CREATE SET par.name=$parent "
                        "MERGE (iss)-[:ROLLS_UP_TO]->(par)",
                        issid="iss_" + p["issuer_name"].lower().replace(" ", "_"),
                        parid="iss_" + p["parent_issuer"].lower().replace(" ", "_"),
                        parent=p["parent_issuer"],
                    )
        return {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                "positions": len(positions)}

    def _q(self, cypher: str, **params) -> list[dict]:
        with self.driver.session() as s:
            return [r.data() for r in s.run(cypher, **params)]

    def total_nav(self) -> Decimal:
        rows = self._q(
            "MATCH (p:Position) RETURN p.market_value_sgd AS mv ORDER BY p.id"
        )
        return sum((D(r["mv"]) for r in rows), Decimal(0))

    def asset_class_view(self, name: str) -> dict:
        rows = self._q(
            "MATCH (ac:AssetClass {name:$n})-[:HAS_LIMIT]->(l:Limit) "
            "RETURN ac.code AS code, properties(l) AS lim, l.provenance AS prov",
            n=name,
        )
        if not rows:
            raise KeyError(f"AssetClass not in graph: {name}")
        lim = dict(rows[0]["lim"]); lim.pop("provenance", None)
        positions = self._q(
            "MATCH (p:Position)-[:IN_ASSET_CLASS]->(ac:AssetClass {name:$n}) "
            "RETURN properties(p) AS p ORDER BY p.id", n=name,
        )
        return {
            "code": rows[0]["code"], "name": name, "limit": lim,
            "provenance": json.loads(rows[0]["prov"]),
            "positions": [self._pos(r["p"]) for r in positions],
        }

    def non_ig_view(self) -> dict:
        classes = self._q(
            "MATCH (ac:AssetClass)-[:CONTRIBUTES_TO]->(:Aggregate {name:'non_ig'}) "
            "RETURN ac.code AS code, ac.name AS name ORDER BY ac.code"
        )
        lim = self._q(
            "MATCH (:Aggregate {name:'non_ig'})-[:HAS_LIMIT]->(l:Limit) "
            "RETURN properties(l) AS lim, l.provenance AS prov"
        )[0]
        limd = dict(lim["lim"]); limd.pop("provenance", None)
        return {
            "aggregate_code": "non_ig",
            "contributing_classes": [{"code": c["code"], "name": c["name"]} for c in classes],
            "limit": limd, "provenance": json.loads(lim["prov"]),
        }

    def cap_view(self, name: str) -> dict:
        rows = self._q(
            "MATCH (c:Cap {name:$n}) RETURN properties(c) AS c, c.provenance AS prov",
            n=name)
        if not rows:
            raise KeyError(f"Cap not in graph: {name}")
        c = dict(rows[0]["c"]); c.pop("provenance", None)
        return {"code": name, "limit": c, "provenance": json.loads(rows[0]["prov"])}

    def floor_view(self, name: str) -> dict:
        rows = self._q(
            "MATCH (f:Floor {name:$n}) RETURN properties(f) AS f, f.provenance AS prov",
            n=name)
        if not rows:
            raise KeyError(f"Floor not in graph: {name}")
        f = dict(rows[0]["f"]); f.pop("provenance", None)
        return {"code": name, "limit": f, "provenance": json.loads(rows[0]["prov"])}

    def risk_metric_view(self, name: str) -> dict:
        rows = self._q(
            "MATCH (rm:RiskMetric {name:$n})-[:HAS_THRESHOLD]->(t:Threshold) "
            "OPTIONAL MATCH (rm)-[:HAS_BREACH_ACTION]->(ba:BreachAction) "
            "OPTIONAL MATCH (ba)-[:OWNED_BY]->(o:Owner) "
            "RETURN rm.label AS label, properties(t) AS thr, t.provenance AS prov, "
            "properties(ba) AS ba, properties(o) AS owner", n=name,
        )
        if not rows:
            raise KeyError(f"RiskMetric not in graph: {name}")
        r = rows[0]
        thr = dict(r["thr"]); thr.pop("provenance", None)
        ba = dict(r["ba"]) if r["ba"] else None
        if ba:
            ba.pop("provenance", None)
        owner = dict(r["owner"]) if r["owner"] else None
        if owner:
            owner.pop("provenance", None)
        return {"code": name, "label": r["label"], "threshold": thr,
                "breach_action": ba, "owner": owner,
                "provenance": json.loads(r["prov"])}

    def issuer_exposures(self, issuer_type: str, group_by: str) -> list[dict]:
        if group_by == "parent_issuer":
            rows = self._q(
                "MATCH (p:Position {issuer_type:$t})-[:ISSUED_BY]->(iss:Issuer) "
                "OPTIONAL MATCH (iss)-[:ROLLS_UP_TO]->(par:Issuer) "
                "WITH coalesce(par.name, iss.name) AS key, p "
                "RETURN key, p.market_value_sgd AS mv, p.id AS iid, "
                "p.issuer_name AS issuer ORDER BY p.id", t=issuer_type,
            )
        else:
            rows = self._q(
                "MATCH (p:Position {issuer_type:$t})-[:ISSUED_BY]->(iss:Issuer) "
                "RETURN iss.name AS key, p.market_value_sgd AS mv, p.id AS iid, "
                "p.issuer_name AS issuer ORDER BY p.id", t=issuer_type,
            )
        buckets: dict[str, dict] = {}
        for r in rows:
            b = buckets.setdefault(r["key"], {"key": r["key"],
                                              "market_value": Decimal(0),
                                              "instruments": [], "issuers": set()})
            b["market_value"] += D(r["mv"])
            b["instruments"].append(r["iid"])
            b["issuers"].add(r["issuer"])
        out = [{"key": b["key"], "market_value": b["market_value"],
                "instruments": sorted(b["instruments"]),
                "issuers": sorted(b["issuers"])} for b in buckets.values()]
        out.sort(key=lambda x: (-x["market_value"], x["key"]))
        return out

    def all_positions(self) -> list[dict]:
        rows = self._q("MATCH (p:Position) RETURN properties(p) AS p ORDER BY p.id")
        return [self._pos(r["p"]) for r in rows]

    @staticmethod
    def _pos(p: dict) -> dict:
        p = dict(p)
        p.pop("provenance", None)
        return p

    def close(self) -> None:
        self.driver.close()


def make_client(backend: str, *, uri: str = "", user: str = "", password: str = ""):
    if backend == "neo4j":
        return Neo4jClient(uri, user, password)
    return EmbeddedClient()
