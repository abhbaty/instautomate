"""
REST API routes for campaign and config management.

All endpoints return JSON and are consumed by the vanilla JS dashboard.

Campaigns
  GET    /api/campaigns           — List all campaigns
  POST   /api/campaigns           — Create a new campaign
  GET    /api/campaigns/{id}      — Get single campaign
  PUT    /api/campaigns/{id}      — Update campaign
  DELETE /api/campaigns/{id}      — Delete campaign
  PATCH  /api/campaigns/{id}/toggle — Toggle active state

Config
  GET    /api/config              — Get all config keys (values masked for tokens)
  POST   /api/config              — Set a config key

Posts
  GET    /api/post-preview?post_id=… — Fetch post thumbnail + caption from IG
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Campaign, Config, ProcessedComment
import instagram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CampaignCreate(BaseModel):
    name: str
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool = True


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    post_id: Optional[str] = None
    keywords: Optional[str] = None
    comment_reply: Optional[str] = None
    dm_message: Optional[str] = None
    is_active: Optional[bool] = None


class ConfigSet(BaseModel):
    key: str
    value: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _campaign_to_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "post_id": c.post_id,
        "post_caption": c.post_caption,
        "post_thumbnail_url": c.post_thumbnail_url,
        "keywords": c.keywords,
        "comment_reply": c.comment_reply,
        "dm_message": c.dm_message,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _get_access_token(db: Session) -> str:
    row = db.query(Config).filter(Config.key == "INSTAGRAM_ACCESS_TOKEN").first()
    if row and row.value:
        return row.value
    return os.getenv("INSTAGRAM_ACCESS_TOKEN", "")


# ---------------------------------------------------------------------------
# Campaign endpoints
# ---------------------------------------------------------------------------

@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [_campaign_to_dict(c) for c in campaigns]


@router.post("/campaigns", status_code=201)
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db)):
    # Try to fetch post details for thumbnail/caption
    post_caption = ""
    post_thumbnail_url = ""
    try:
        token = _get_access_token(db)
        if token:
            details = instagram.get_post_details(body.post_id, access_token=token)
            post_caption = details.get("caption", "")
            post_thumbnail_url = details.get("thumbnail_url", "")
    except Exception as exc:
        logger.warning("Could not fetch post details for %s: %s", body.post_id, exc)

    campaign = Campaign(
        name=body.name,
        post_id=body.post_id,
        post_caption=post_caption,
        post_thumbnail_url=post_thumbnail_url,
        keywords=body.keywords,
        comment_reply=body.comment_reply,
        dm_message=body.dm_message,
        is_active=body.is_active,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign_to_dict(campaign)


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _campaign_to_dict(c)


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, body: CampaignUpdate, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if body.name is not None:
        c.name = body.name
    if body.post_id is not None:
        c.post_id = body.post_id
        # Re-fetch post details if post_id changed
        try:
            token = _get_access_token(db)
            if token:
                details = instagram.get_post_details(body.post_id, access_token=token)
                c.post_caption = details.get("caption", "")
                c.post_thumbnail_url = details.get("thumbnail_url", "")
        except Exception as exc:
            logger.warning("Could not refresh post details: %s", exc)
    if body.keywords is not None:
        c.keywords = body.keywords
    if body.comment_reply is not None:
        c.comment_reply = body.comment_reply
    if body.dm_message is not None:
        c.dm_message = body.dm_message
    if body.is_active is not None:
        c.is_active = body.is_active

    db.commit()
    db.refresh(c)
    return _campaign_to_dict(c)


@router.delete("/campaigns/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(c)
    db.commit()
    return None


@router.patch("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    c.is_active = not c.is_active
    db.commit()
    db.refresh(c)
    return {"id": c.id, "is_active": c.is_active}


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

SENSITIVE_KEYS = {"INSTAGRAM_ACCESS_TOKEN", "FACEBOOK_APP_SECRET", "WEBHOOK_VERIFY_TOKEN"}


@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    rows = db.query(Config).all()
    result = {}
    for row in rows:
        if row.key in SENSITIVE_KEYS and row.value:
            # Mask sensitive values — show only last 6 chars
            result[row.key] = "••••••" + row.value[-6:]
        else:
            result[row.key] = row.value
    return result


@router.post("/config")
def set_config(body: ConfigSet, db: Session = Depends(get_db)):
    row = db.query(Config).filter(Config.key == body.key).first()
    if row:
        row.value = body.value
    else:
        row = Config(key=body.key, value=body.value)
        db.add(row)
    db.commit()
    return {"status": "saved", "key": body.key}


# ---------------------------------------------------------------------------
# Post preview endpoint
# ---------------------------------------------------------------------------

@router.get("/post-preview")
def post_preview(post_id: str, db: Session = Depends(get_db)):
    """Fetch post metadata to show a preview when the user enters a Post ID."""
    token = _get_access_token(db)
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Instagram access token not configured. Save it in Settings first.",
        )
    try:
        details = instagram.get_post_details(post_id, access_token=token)
        return {
            "post_id": post_id,
            "caption": details.get("caption", ""),
            "thumbnail_url": details.get("thumbnail_url", ""),
            "media_type": details.get("media_type", ""),
            "permalink": details.get("permalink", ""),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return quick stats for the dashboard header."""
    total_campaigns = db.query(Campaign).count()
    active_campaigns = db.query(Campaign).filter(Campaign.is_active == True).count()
    total_processed = db.query(ProcessedComment).count()
    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_processed_comments": total_processed,
    }
