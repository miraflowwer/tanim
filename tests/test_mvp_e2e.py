import http.client
import importlib.util
import json
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_service():
    path = ROOT / "scripts" / "service.py"
    spec = importlib.util.spec_from_file_location("tanim_service_e2e", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def demo_payload(crop, area):
    count = 4 if crop == "tomato" else 2
    each_area = area / count
    return {
        "plans": [
            {
                "crop": crop,
                "region_id": "IV-A",
                "location": "Tanauan, Batangas",
                "farm_size_ha": each_area,
                "farm_size_margin_ha": 0.0,
                "planting_date": "2026-09-01",
                "harvest_period": "2026-12",
            }
            for _ in range(count)
        ],
        "use_demo_reference": True,
    }


def normal_frontend_payload():
    """Payload produced by the normal PlanForm through toBackendPayload()."""
    return {
        "use_demo_reference": False,
        "plan": {
            "crop": "tomato",
            "region_id": "IV-A",
            "location": "Tanauan, Batangas",
            "farm_size_ha": 2.0,
            "farm_size_margin_ha": 0.0,
            "planting_date": "2026-09-01",
            "harvest_period": "2026-12",
        },
        "comparison": {
            "amount": 100.0,
            "unit": "MT",
            "type": "historical_production_baseline",
            "geography": "CALABARZON (IV-A)",
            "period": "2021-2025",
            "region_id": "IV-A",
        },
        "source_labels": ["PSA OpenSTAT table"],
    }


def post_json(port, path, payload):
    body = json.dumps(payload).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(
        "POST",
        path,
        body=body,
        headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    return response.status, json.loads(data)


def get_json(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path, headers={"Accept": "application/json"})
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    return response.status, json.loads(data)


def test_http_api_runs_fixed_tomato_demo_end_to_end():
    service = load_service()
    server = service.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        service.GrciRequestHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, envelope = post_json(
            server.server_port,
            "/api/grci",
            demo_payload("tomato", 40.0),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 200
    assert envelope["error"] is None
    result = envelope["result"]
    assert envelope["lookup"]["plan_count"] == 4
    assert result["expected_production_range"] == [600.0, 600.0]
    assert result["risk_state"] == "high"
    assert result["reference_quality"] == "synthetic"
    assert result["evidence_status"] == "fixed_synthetic"
    assert result["market_demand_wording_allowed"] is False


def test_http_api_runs_fixed_eggplant_demo_end_to_end():
    service = load_service()
    server = service.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        service.GrciRequestHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, envelope = post_json(
            server.server_port,
            "/api/grci",
            demo_payload("eggplant", 8.0),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 200
    assert envelope["lookup"]["plan_count"] == 2
    assert envelope["result"]["expected_production_range"] == [96.0, 96.0]
    assert envelope["result"]["risk_state"] == "low"
    assert envelope["result"]["evidence_status"] == "fixed_synthetic"


def test_http_api_runs_normal_frontend_payload_end_to_end():
    service = load_service()
    server = service.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        service.GrciRequestHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, envelope = post_json(
            server.server_port,
            "/api/grci",
            normal_frontend_payload(),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 200
    assert envelope["error"] is None
    assert envelope["lookup"]["plan_count"] == 1
    result = envelope["result"]
    assert result["status"] == "unclassified"
    assert result["reference_type"] == "historical_production_baseline"
    assert result["expected_production_range"] == [27.8924, 27.8924]
    assert result["evidence_status"] == "user_provided_unverified"
    assert result["evidence_verified"] is False
    assert result["market_demand_wording_allowed"] is False


def test_http_api_rejects_user_entered_direct_demand():
    service = load_service()
    server = service.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        service.GrciRequestHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = normal_frontend_payload()
        payload["comparison"]["type"] = "local_committed_demand"
        status, envelope = post_json(server.server_port, "/api/grci", payload)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 400
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "invalid_input"
    assert "reviewed/verified" in envelope["error"]["message"]


def test_http_api_rejects_untraceable_normal_plan():
    service = load_service()
    server = service.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        service.GrciRequestHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = {
            "plan": {
                "crop": "tomato",
                "region_id": "IV-A",
                "location": "Tanauan, Batangas",
                "farm_size_ha": 2.0,
                "farm_size_margin_ha": 0.0,
                "planting_date": "2026-09-01",
                "harvest_period": "2026-12",
            },
            "use_demo_reference": False,
        }
        status, envelope = post_json(server.server_port, "/api/grci", payload)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 400
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "comparison_required"


def test_frontend_contract_matches_service_envelope():
    client = (ROOT / "web" / "src" / "api" / "grciClient.js").read_text(
        encoding="utf-8"
    )
    payload = (ROOT / "web" / "src" / "api" / "grciPayload.js").read_text(
        encoding="utf-8"
    )
    app = (ROOT / "web" / "src" / "App.jsx").read_text(encoding="utf-8")
    form = (ROOT / "web" / "src" / "components" / "PlanForm.jsx").read_text(
        encoding="utf-8"
    )
    result_card = (ROOT / "web" / "src" / "components" / "ResultCard.jsx").read_text(
        encoding="utf-8"
    )
    assert "payload.plan = toPlanRecord(planInput)" in payload
    assert "payload.plans = planInput.plans.map(toPlanRecord)" in payload
    assert "payload.comparison" in payload
    assert "payload.source_labels" in payload
    assert "fetchOptions" in client
    assert "envelope?.error" in client
    assert "return envelope.result" in client
    assert "preset={presetPlan}" in app
    assert "options={options}" in app
    assert "Array.from({ length: count }" in app
    assert "Comparison evidence" in form
    assert "referenceTypes" in form
    assert "local_committed_demand" not in form
    assert 'type="checkbox"' not in form
    assert "user_provided_unverified" in result_card
    assert "reviewed_verified" in result_card
    assert "reference_mode" in result_card
    assert "Demo risk state" in result_card
    assert "Proxy risk state" in result_card
    assert "COMMITTED LOCAL" not in result_card
    assert 'min="0.1"' in form
    assert "Harvest month cannot be before the planting month." in form


def test_frontend_mock_fallback_contains_only_fixed_synthetic_fixtures():
    mocks = (ROOT / "web" / "src" / "mocks" / "grciMocks.js").read_text(
        encoding="utf-8"
    )
    assert '"tomato-demo"' in mocks
    assert '"eggplant-demo"' in mocks
    assert "local_committed_demand" not in mocks
    assert "LGU Tanauan offtake" not in mocks
    assert "1000000.0" not in mocks


def test_demo_runbook_matches_locked_values():
    runbook = (ROOT / "docs" / "DEMO_RUNBOOK.md").read_text(encoding="utf-8")
    for text in (
        "40 ha",
        "600 MT",
        "1.6",
        "8 ha",
        "96 MT",
        "0.53",
        "DEMO-2026",
        "user_provided_unverified",
    ):
        assert text in runbook

    design = (ROOT / "docs" / "WEB_DESIGN.md").read_text(encoding="utf-8")
    assert "user_provided_unverified" in design
    assert "local_committed_demand" in design
    assert "COMMITTED LOCAL" not in design


def test_live_demo_has_no_external_network_dependency():
    service_text = (ROOT / "scripts" / "service.py").read_text(encoding="utf-8")
    assert "urllib.request" not in service_text
    assert "api.openstat.psa.gov.ph" not in service_text
    assert "http.server" in service_text


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} MVP end-to-end checks passed")
