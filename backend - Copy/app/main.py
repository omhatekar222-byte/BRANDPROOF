import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import Base, SessionLocal, engine, get_db
from app.routers import (
    admin, analytics, auth, campaigns, content, impact, intelligence, knowledge, notifications, review, wallet,
)
from app.services import ai
from app.services.seed import ensure_nova_demo, seed_demo

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "BrandProof keeps marketing claims answerable: every statement is checked against approved "
    "company knowledge, reviewer decisions feed guideline improvements, and product changes are "
    "traced back to affected content. Missing evidence is reported as unverified, never as false."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.SEED_DEMO_DATA:
        db = SessionLocal()
        try:
            seed_demo(db)
            ensure_nova_demo(db)
        except Exception:  # pragma: no cover - startup should not crash on seed issues
            db.rollback()
            raise
        finally:
            db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=DESCRIPTION,
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Preserve HTTPException semantics; only convert unexpected failures.
    from starlette.exceptions import HTTPException as StarletteHTTPException

    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    detail = "An unexpected server error occurred."
    if settings.ENV != "production":
        detail = f"{type(exc).__name__}: {exc}"
    return JSONResponse(status_code=500, content={"detail": detail})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, knowledge, content, review, intelligence, impact, analytics, admin, notifications, wallet):
    app.include_router(module.router, prefix=settings.API_PREFIX)

app.include_router(campaigns.router, prefix=settings.API_PREFIX)
app.include_router(campaigns.tasks_router, prefix=settings.API_PREFIX)

# Uploaded brand assets are served read-only for the workspace UI.
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get(f"{settings.API_PREFIX}/public/organisation", tags=["System"])
def public_organisation(db: Session = Depends(get_db)):
    """Public organisation profile (contact placeholders shown on the website until
    an administrator supplies real details). Only admin-configured settings are
    exposed — never private knowledge and never invented details."""
    from app.models import Organisation
    org = db.scalars(select(Organisation).where(Organisation.slug == "novatech")).first()
    contact = (org.settings or {}) if org else {}
    return {
        "company_name": org.name if org else settings.APP_NAME,
        "contact_email": contact.get("contact_email", ""),
        "contact_phone": contact.get("contact_phone", ""),
        "contact_address": contact.get("contact_address", ""),
        "support_note": "Contact your workspace administrator.",
    }


@app.get(f"{settings.API_PREFIX}/health", tags=["System"])
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.ENV,
        "ai": ai.status(),
        "demo_data": settings.SEED_DEMO_DATA,
    }


@app.get(f"{settings.API_PREFIX}/meta/options", tags=["System"])
def options() -> dict:
    return {
        "roles": [
            {"value": "admin", "label": "Administrator"},
            {"value": "content_creator", "label": "Content Creator"},
            {"value": "reviewer", "label": "Reviewer"},
            {"value": "approver", "label": "Approver"},
        ],
        "content_types": [
            {"value": "advertisement", "label": "Advertisement"},
            {"value": "social_post", "label": "Social post"},
            {"value": "product_description", "label": "Product description"},
            {"value": "email", "label": "Email"},
            {"value": "landing_page", "label": "Landing page"},
            {"value": "press_release", "label": "Press release"},
            {"value": "document", "label": "Document"},
            {"value": "presentation", "label": "Presentation"},
        ],
        "doc_types": [
            {"value": "guideline", "label": "Guideline"},
            {"value": "product_spec", "label": "Product specification"},
            {"value": "company_info", "label": "Company information"},
            {"value": "approved_claim", "label": "Approved claim"},
            {"value": "terminology", "label": "Terminology"},
            {"value": "asset", "label": "Asset"},
            {"value": "warranty_pricing", "label": "Warranty & pricing"},
            {"value": "restricted_language", "label": "Restricted language"},
        ],
        "content_statuses": ["draft", "submitted", "under_review", "changes_requested", "approved", "rejected", "cleared_by_policy"],
        "submission_statuses": ["draft", "submitted", "under_review", "changes_requested", "approved", "rejected", "cleared_by_policy"],
        "document_statuses": ["draft", "approved", "archived", "outdated"],
        "claim_statuses": ["approved", "prohibited", "draft"],
        "fact_statuses": ["draft", "approved", "retired"],
        "guideline_statuses": ["draft", "approved", "archived"],
        "finding_statuses": ["open", "accepted", "rejected", "modified", "resolved"],
        "severities": ["low", "medium", "high", "critical"],
        "proof_statuses": ["supported", "contradicted", "unsupported", "inconclusive", "pending"],
        "impact_statuses": ["open", "recheck_requested", "resolved"],
    }
