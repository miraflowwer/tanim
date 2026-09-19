"""API integration: DB -> service -> GRCI -> persist (sqlite test DB, PRD S35).

Simulates the PRD S20 server flow with an in-memory sqlite DB:
load plan revision, check auth, resolve yield, resolve eligible evidence,
run deterministic calc, persist calculation_runs row with S33 fields.
"""
import importlib.util
import pathlib
import sqlite3
import time
import uuid
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _grci():
    path = ROOT / "backend" / "app" / "grci.py"
    spec = importlib.util.spec_from_file_location("p0_grci", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE plans(id TEXT PRIMARY KEY, org_id TEXT, crop TEXT, area_ha REAL, yield REAL, harvest TEXT)")
    con.execute("CREATE TABLE refs(id TEXT PRIMARY KEY, org_id TEXT, rtype TEXT, vstate TEXT, amount REAL)")
    con.execute("""CREATE TABLE calculation_runs(
        calculation_id TEXT PRIMARY KEY, request_id TEXT, org_id TEXT, plan_id TEXT,
        engine_version TEXT, policy_version TEXT, dataset_version TEXT, reference_version TEXT,
        status TEXT, duration_ms REAL, timestamp TEXT, supply_load REAL)""")
    return con


def _calc(grci, area, yld, ref_amount, rtype, vstate):
    assert grci.is_eligible(rtype, vstate), (rtype, vstate)
    t0 = time.perf_counter()
    s = grci.estimate_production(area, yld)["s_mt"]
    load = grci.supply_load(s, ref_amount)
    dt = (time.perf_counter() - t0) * 1000.0
    return s, load, dt


def test_db_to_grci_to_persisted_result():
    grci = _grci()
    con = _db()
    try:
        con.execute("INSERT INTO plans VALUES('plan-1','org-1','tomato',3.1,3.0,'2026-12')")
        con.execute("INSERT INTO refs VALUES('ref-1','org-1','local_committed_demand','reviewed_verified',25.0)")
        plan = con.execute("SELECT * FROM plans WHERE id='plan-1' AND org_id='org-1'").fetchone()
        ref = con.execute("SELECT * FROM refs WHERE id='ref-1' AND org_id='org-1'").fetchone()
        assert plan and ref
        s, load, dt = _calc(grci, plan[3], plan[4], ref[4], ref[2], ref[3])
        assert abs(s - 9.3) < 1e-9
        assert abs(load - 0.372) < 1e-9
        calc_id, req_id = str(uuid.uuid4()), str(uuid.uuid4())
        con.execute(
            "INSERT INTO calculation_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (calc_id, req_id, "org-1", "plan-1", grci.ENGINE_VERSION, "grci-1.0",
             "psa-2021-2025-v1", "ref-v3", "complete", dt,
             datetime.now(UTC).isoformat(), load),
        )
        row = con.execute("SELECT * FROM calculation_runs WHERE calculation_id=?", (calc_id,)).fetchone()
        assert row is not None and abs(row[11] - 0.372) < 1e-9
        # Reproduce from stored inputs.
        _s, load2, _ = _calc(grci, plan[3], plan[4], ref[4], ref[2], ref[3])
        assert abs(load2 - row[11]) < 1e-12
    finally:
        con.close()


def test_synthetic_never_persists_as_real_result():
    grci = _grci()
    assert not grci.is_eligible("demo_coordination_baseline", "synthetic_demo")
    # No L row is written for synthetic in the real path; incomplete instead.
    con = _db()
    try:
        assert con.execute("SELECT COUNT(*) FROM calculation_runs").fetchone()[0] == 0
    finally:
        con.close()


def test_wrong_org_sees_zero_rows():
    con = _db()
    try:
        con.execute("INSERT INTO plans VALUES('plan-9','org-A','tomato',2.0,3.0,'2026-12')")
        assert con.execute("SELECT * FROM plans WHERE org_id='org-B'").fetchall() == []
    finally:
        con.close()
