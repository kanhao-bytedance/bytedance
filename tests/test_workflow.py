from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.db import Base
from app.schemas import Classification, RawFeedback
from app.services import classifier


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(main.settings, "openai_api_key", None)
    monkeypatch.setattr(main.settings, "reddit_bearer_token", None)
    with TestClient(main.app) as client:
        yield client
    engine.dispose()


def item(external_id="one", **kwargs):
    return dict(source="manual", external_id=external_id, content_type="comment",
                title="Auction timer", text="Please extend the timer when a buyer bids.", **kwargs)


def test_ingest_dedup_search_evidence_and_pagination(client):
    first = client.post("/ingest", json=item()).json()
    assert first["created"] is True
    assert first["classification_status"] == "unclassified"
    duplicate = client.post("/ingest", json=item()).json()
    assert duplicate["id"] == first["id"]
    assert duplicate["created"] is False
    assert client.get("/summary").json()["total"] == 1
    evidence = client.get(f'/feedback/{first["id"]}').json()
    assert evidence["text"] == item()["text"]
    assert evidence["relevance"] == 0
    assert evidence["external_id"] == "one"
    assert len(client.get("/feedback", params={"q":"timer"}).json()) == 1
    assert client.get("/feedback", params={"q":"no matching words"}).json() == []
    assert client.get("/feedback", params={"offset":1}).json() == []
    assert client.get("/feedback/999").status_code == 404
    # SQL wildcard characters are literal search text.
    assert client.get("/feedback", params={"q":"%"}).json() == []
    assert client.get("/summary", params={"q":"unmatched"}).json()["total"] == 0


def test_classified_filters_and_trends(client, monkeypatch):
    monkeypatch.setattr(main.settings, "openai_api_key", "test-only")
    monkeypatch.setattr(main, "classify", lambda raw: Classification(
        relevant=True, relevance=.95, platform="Whatnot", product_area="Auction",
        feedback_type="Feature Request", sentiment="Negative", severity="High", summary="Extend the timer"))
    assert client.post("/ingest", json=item()).status_code == 200
    assert client.post("/ingest", json=item("two")).status_code == 200
    query = {"platform":"Whatnot", "severity":"High", "feedback_type":"Feature Request"}
    assert len(client.get("/feedback", params={**query, "limit":1}).json()) == 1
    summary = client.get("/summary", params=query).json()
    assert summary == dict(total=2, high_severity=2, feature_requests=2, unclassified=0,
                           platforms=[{"name":"Whatnot", "count":2}])
    assert client.get("/trends", params=query).json() == [
        {"product_area":"Auction", "feedback_type":"Feature Request", "count":2}]
    assert client.get("/feedback", params={"platform":"eBay"}).json() == []
    assert client.get("/trends", params={"platform":"eBay"}).json() == []


@pytest.mark.parametrize("params", [{"limit":0}, {"limit":501}, {"offset":-1}])
def test_bad_pagination(client, params):
    assert client.get("/feedback", params=params).status_code == 422


@pytest.mark.parametrize("field,value", [("source"," "), ("external_id",""), ("text"," "), ("content_type","")])
def test_empty_input(client, field, value):
    payload = item()
    payload[field] = value
    assert client.post("/ingest", json=payload).status_code == 422
    assert client.get("/summary").json()["total"] == 0


def test_missing_reddit_credentials_and_invalid_limits(client):
    response = client.post("/collect/reddit", params={"q":"auctions"})
    assert response.status_code == 503
    assert "REDDIT_BEARER_TOKEN" in response.json()["detail"]
    assert client.post("/collect/reddit", params={"q":"auctions", "limit":0}).status_code == 422
    assert client.post("/collect/reddit", params={"q":"auctions", "subreddit":"../bad"}).status_code == 422


def test_reddit_collection_deduplicates_and_handles_upstream_error(client, monkeypatch):
    monkeypatch.setattr(main.settings, "reddit_bearer_token", "test-only")
    async def search(*args):
        return [RawFeedback(**item())]
    monkeypatch.setattr(main, "search_posts", search)
    assert client.post("/collect/reddit", params={"q":"auctions"}).json() == {"fetched":1, "created":1}
    assert client.post("/collect/reddit", params={"q":"auctions"}).json() == {"fetched":1, "created":0}
    async def fail(*args):
        raise httpx.ConnectError("private upstream error")
    monkeypatch.setattr(main, "search_posts", fail)
    response = client.post("/collect/reddit", params={"q":"auctions"})
    assert response.status_code == 502
    assert "private upstream error" not in response.text


def test_classifier_strict_schema_and_quoted_content(monkeypatch):
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_text=Classification(relevant=True, relevance=.8, summary="Feedback").model_dump_json())
    monkeypatch.setattr(classifier.settings, "openai_api_key", "test-only")
    monkeypatch.setattr(classifier, "OpenAI", lambda **kw: SimpleNamespace(responses=SimpleNamespace(create=create)))
    result = classifier.classify(RawFeedback(**item()))
    assert result.summary == "Feedback"
    schema = captured["text"]["format"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert item()["text"] in captured["input"]


def test_bad_ai_response_does_not_store_record(client, monkeypatch):
    def fail(raw):
        raise ValueError("invalid response with private details")
    monkeypatch.setattr(main, "classify", fail)
    response = client.post("/ingest", json=item())
    assert response.status_code == 502
    assert "private details" not in response.text
    assert client.get("/summary").json()["total"] == 0


def test_dashboard_and_health(client):
    assert "A clearer view of your customers" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/health").json() == {"ok":True, "ai_enabled":False, "reddit_enabled":False}
