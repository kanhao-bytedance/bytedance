from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .db import Base, engine, SessionLocal
from .models import Feedback
from .schemas import RawFeedback
from .services.classifier import classify
from .collectors.reddit import search_posts
from .settings import settings


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Live Commerce Voice of Customer", version="0.2.0", lifespan=lifespan)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def db():
    with SessionLocal() as session:
        yield session


def save_item(session: Session, raw: RawFeedback):
    identity = (Feedback.source == raw.source, Feedback.external_id == raw.external_id)
    existing = session.scalar(select(Feedback).where(*identity))
    if existing:
        return existing, False
    classification = classify(raw)
    row = Feedback(**raw.model_dump(), **classification.model_dump(),
                   classification_status="classified" if settings.openai_api_key else "unclassified")
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(Feedback).where(*identity))
        if existing is None:
            raise
        return existing, False
    session.refresh(row)
    return row, True


def serialize(row):
    return {column.name: getattr(row, column.name) for column in Feedback.__table__.columns}


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health(session: Session = Depends(db)):
    session.execute(select(1))
    return {"ok": True, "ai_enabled": bool(settings.openai_api_key),
            "reddit_enabled": bool(settings.reddit_bearer_token)}


@app.post("/ingest")
def ingest(raw: RawFeedback, session: Session = Depends(db)):
    try:
        row, created = save_item(session, raw)
    except (OpenAIError, ValueError) as exc:
        raise HTTPException(502, "Classification failed. Check the configured model and API access.") from exc
    return {"id": row.id, "created": created, "summary": row.summary,
            "classification_status": row.classification_status}


def store_batch(items):
    with SessionLocal() as session:
        return sum(int(save_item(session, item)[1]) for item in items)


@app.post("/collect/reddit")
async def collect_reddit(q: str = Query(..., min_length=1, max_length=500),
                         subreddit: str | None = Query(None, pattern=r"^[A-Za-z0-9_]{1,21}$"),
                         limit: int = Query(25, ge=1, le=100)):
    if not settings.reddit_bearer_token:
        raise HTTPException(503, "Configure REDDIT_BEARER_TOKEN to enable Reddit collection.")
    try:
        items = await search_posts(q, subreddit, limit)
        created = await run_in_threadpool(store_batch, items)
    except (httpx.HTTPError, OpenAIError, ValueError, KeyError) as exc:
        raise HTTPException(502, "Collection could not complete. Some records may already be saved; retrying is safe.") from exc
    return {"fetched": len(items), "created": created}


def filters(platform=None, product_area=None, feedback_type=None, q=None, severity=None,
            sentiment=None, source=None, classification_status=None):
    clauses = []
    for name, value in dict(platform=platform, product_area=product_area, feedback_type=feedback_type,
                            severity=severity, sentiment=sentiment, source=source,
                            classification_status=classification_status).items():
        if value:
            clauses.append(getattr(Feedback, name) == value)
    if q:
        clauses.append(or_(*(column.contains(q, autoescape=True) for column in
                             [Feedback.title, Feedback.text, Feedback.summary, Feedback.requested_change])))
    return clauses


def query_filters(platform: str | None = None, product_area: str | None = None,
                  feedback_type: str | None = None, q: str | None = Query(None, max_length=500),
                  severity: str | None = None, sentiment: str | None = None,
                  source: str | None = None, classification_status: str | None = None):
    return filters(platform, product_area, feedback_type, q, severity, sentiment, source, classification_status)


@app.get("/feedback")
def feedback(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
             clauses: list = Depends(query_filters), session: Session = Depends(db)):
    stmt = (select(Feedback).where(*clauses)
            .order_by(Feedback.created_at.desc(), Feedback.id.desc()).offset(offset).limit(limit))
    return [serialize(row) for row in session.scalars(stmt)]


@app.get("/feedback/{feedback_id}")
def feedback_detail(feedback_id: int, session: Session = Depends(db)):
    row = session.get(Feedback, feedback_id)
    if row is None:
        raise HTTPException(404, "Feedback not found")
    return serialize(row)


@app.get("/summary")
def summary(clauses: list = Depends(query_filters), session: Session = Depends(db)):
    def count(*extra):
        return session.scalar(select(func.count(Feedback.id)).where(*clauses, *extra))
    platforms = session.execute(select(Feedback.platform, func.count(Feedback.id)).where(*clauses)
                                .group_by(Feedback.platform)).all()
    return {"total": count(), "high_severity": count(Feedback.severity.in_(["High", "Critical"])),
            "feature_requests": count(Feedback.feedback_type == "Feature Request"),
            "unclassified": count(Feedback.classification_status == "unclassified"),
            "platforms": [{"name": name or "Other", "count": n} for name, n in platforms]}


@app.get("/trends")
def trends(clauses: list = Depends(query_filters), session: Session = Depends(db)):
    rows = session.execute(select(Feedback.product_area, Feedback.feedback_type, func.count(Feedback.id))
                           .where(*clauses).group_by(Feedback.product_area, Feedback.feedback_type)
                           .order_by(func.count(Feedback.id).desc(), Feedback.product_area, Feedback.feedback_type)).all()
    return [{"product_area": area or "Other", "feedback_type": kind or "Other", "count": n}
            for area, kind, n in rows]
