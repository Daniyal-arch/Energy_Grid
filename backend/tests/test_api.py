import json

import pytest
from fastapi.testclient import TestClient

from agent.limits import get_limits
from app.main import app, settings


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def sse(text, run=False):
    """(event, data) pairs; the `run` event (the run id, brief 30) only when asked."""
    out = []
    for block in text.strip().split("\n\n"):
        lines = [x for x in block.split("\n") if not x.startswith("id: ")]
        if lines and lines[0].startswith("event: "):
            out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out if run else [e for e in out if e[0] != "run"]


def test_health(client):
    r = client.get("/api/health")
    j = r.json()
    assert r.status_code == 200 and j["models"] == {"main": "fake", "fast": "fake"}
    assert j["lake"]["catalog_updated"] == "2026-10-27T00:00:00Z"
    assert r.headers["x-request-id"] and len(r.headers["x-trace-id"]) == 32


def test_cors(client):
    r = client.options(
        "/api/ask",
        headers={"origin": "http://localhost:5173", "access-control-request-method": "POST"},
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = client.options(
        "/api/ask",
        headers={"origin": "https://evil.example", "access-control-request-method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers


def test_data_service_routes_carry_sources(client):
    for path in (
        "/api/catalog/search?q=wind",
        "/api/catalog/registers",
        "/api/places?q=Lyon",
        "/api/site?lon=2.35&lat=48.85",
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.json()["sources"], path
    assert client.get("/api/catalog/nope").status_code == 404


def test_saved_maps_round_trip(client):
    spec = {
        "title": "t",
        "overlays": [
            {
                "id": "a",
                "kind": "points",
                "data": {"result_id": "r_00000000beef", "lon": "lon", "lat": "lat"},
                "legend": {"title": "x", "how": "y"},
                "source": "test rows",
            }
        ],
    }
    body = {
        "spec": spec,
        "data": {"r_00000000beef": {"columns": ["lon", "lat"], "rows": [[4.9, 52.4]]}},
        "sources": [{"dataset": "t", "table": "t", "licence": "l", "retrieved": "r"}],
    }
    r = client.post("/api/maps", json=body)
    assert r.status_code == 200, r.text
    got = client.get(f"/api/maps/{r.json()['id']}").json()
    assert got["spec"]["title"] == "t" and got["data"]["r_00000000beef"]["rows"] == [[4.9, 52.4]]
    assert client.get("/api/maps/m_000000000000").status_code == 404
    spec["overlays"][0]["kind"] = "choropleth"
    assert client.post("/api/maps", json=body).status_code == 422


def test_admin_sql_needs_key(client):
    assert client.post("/api/admin/sql", json={"sql": "SELECT 1"}).status_code == 401
    r = client.post(
        "/api/admin/sql",
        json={"sql": "SELECT count(*) AS n FROM registers.gb"},
        headers={"x-admin-key": "test-admin"},
    )
    assert r.json()["rows"] == [[4]]
    r = client.post(
        "/api/admin/sql", json={"sql": "DROP TABLE x"}, headers={"x-admin-key": "test-admin"}
    )
    assert "refused" in r.json()["error"]


def test_ask_streams_text_tool_map_sources_done(client):
    with client.stream(
        "POST", "/api/ask", json={"question": "Show the largest power plants in Germany on a map"}
    ) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        events = sse(r.read().decode())
    kinds = [e for e, _ in events]
    # the router's plan first, then the steps, the map design and the map
    assert kinds[0] == "plan" and kinds[1] == "tool" and "text" in kinds and "map" in kinds
    assert "design" in kinds and kinds.index("design") < kinds.index("map")
    assert events[0][1]["map"] is True
    assert kinds[-2:] == ["sources", "done"]
    done = events[-1][1]
    assert len(done["trace_id"]) == 32 and done["grounding"]["score"] == 1.0 and done["maps"]
    text = "".join(d["delta"] for e, d in events if e == "text" and "delta" in d)
    assert text == done["answer"]


def test_ask_model_must_be_allowed(client):
    r = client.post("/api/ask", json={"question": "hi", "model": "openai:gpt-6.1-sol"})
    assert r.status_code == 400


def test_body_size_limit(client):
    r = client.post("/api/ask", content=b"x" * 70_000, headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_rate_limit(client):
    lim = get_limits(settings)
    old = lim.per_hour
    lim.per_hour, lim.buckets = 1, {}
    try:
        assert client.post("/api/ask", json={"question": ""}).status_code == 200
        assert client.post("/api/ask", json={"question": ""}).status_code == 429
    finally:
        lim.per_hour, lim.buckets = old, {}


def test_budget_message_in_stream(client):
    lim = get_limits(settings)
    lim.add_spend(10_000)
    try:
        with client.stream("POST", "/api/ask", json={"question": "anything"}) as r:
            events = sse(r.read().decode())
        assert events[-1][1]["stop"] == "budget" and "budget" in events[-1][1]["answer"]
    finally:
        lim.spend.clear()


def test_proxy_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "require_proxy", True)
    monkeypatch.setattr(settings, "proxy_secret", "s3cret")
    assert client.get("/api/places?q=Lyon").status_code == 403
    assert client.get("/api/places?q=Lyon", headers={"x-atlas-proxy": "s3cret"}).status_code == 200
    assert client.get("/api/health").status_code == 200


def test_ask_resume_after_a_dropped_connection_and_cancel(client):
    with client.stream("POST", "/api/ask", json={"question": "How many plants in Germany?"}) as r:
        rid = r.headers["x-run-id"]
        full = r.read().decode()
    events = sse(full, run=True)
    assert events[0] == ("run", {"run_id": rid}) and events[-1][0] == "done"
    # a client that saw events 0-2 reconnects: it gets 3 onwards, each once
    with client.stream("GET", f"/api/ask/{rid}/stream", headers={"Last-Event-ID": "2"}) as r:
        rest = r.read().decode()
    assert rest.startswith("id: 3\n") and sse(rest, run=True) == events[3:]
    assert client.get(f"/api/ask/{rid}/stream", headers={"Last-Event-ID": "x"}).status_code == 422
    assert client.get("/api/ask/run_nope/stream").status_code == 404
    assert client.post(f"/api/ask/{rid}/cancel").status_code == 404  # finished already


def test_cancel_a_running_run():
    import asyncio

    from app import live_runs

    async def slow():
        yield "event: text\ndata: {}\n\n"
        await asyncio.sleep(30)
        yield "event: done\ndata: {}\n\n"

    async def go():
        run = live_runs.start(slow())
        await asyncio.sleep(0.05)
        assert live_runs.cancel(run.run_id)
        got = [e async for e in live_runs.follow(run)]
        return got

    got = asyncio.run(go())
    assert '"stop": "cancelled"' in got[-1] and len(got) == 3


def test_conversation_permalink(client):
    r = client.post(
        "/api/conversations",
        json={
            "turns": [
                {"role": "user", "text": "Tell me about Luxembourg"},
                {"role": "assistant", "text": "**Luxembourg** ...", "maps": []},
            ]
        },
    )
    cid = r.json()["id"]
    assert r.json()["link"] == f"?chat={cid}"
    got = client.get(f"/api/conversations/{cid}").json()
    assert [t["role"] for t in got["turns"]] == ["user", "assistant"]
    assert client.get("/api/conversations/k_000000000000").status_code == 404
    assert client.get("/api/conversations/../x").status_code == 404
