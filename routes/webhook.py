"""
Webhook endpoints for the Instagram Comment-to-DM Automation Tool.

GET  /webhook/instagram  — Challenge verification (Facebook sends this on subscription)
POST /webhook/instagram  — Receives real-time comment events from Instagram
"""

import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from database import get_db
from models import Campaign, Config, ProcessedComment
import instagram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_config_value(db: Session, key: str, fallback_env: str = "") -> str:
    """Read a config value from DB first, then fall back to env var."""
    row = db.query(Config).filter(Config.key == key).first()
    if row and row.value:
        return row.value
    return os.getenv(fallback_env, "")


def _verify_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Validate the X-Hub-Signature-256 header sent by Meta.
    Returns True if the HMAC-SHA256 of the body matches.
    """
    app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
    if not app_secret:
        logger.warning("FACEBOOK_APP_SECRET is not set — skipping signature verification!")
        return True  # Permissive in dev; REMOVE this in production

    expected_sig = "sha256=" + hmac.new(
        app_secret.encode(), request_body, hashlib.sha256
    ).hexdigest()
    # Note: hmac.new() is the correct Python stdlib function name

    # Use hmac.compare_digest for constant-time comparison
    return hmac.compare_digest(expected_sig, signature_header or "")


# ---------------------------------------------------------------------------
# GET — webhook challenge verification
# ---------------------------------------------------------------------------

@router.get("/instagram")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    db: Session = Depends(get_db),
):
    """
    Facebook/Instagram sends a GET request with a challenge to verify that
    this server controls the webhook URL.  We check the verify token and
    echo back the challenge.
    """
    verify_token = _get_config_value(db, "WEBHOOK_VERIFY_TOKEN", "WEBHOOK_VERIFY_TOKEN")

    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("Webhook verification successful.")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning(
        "Webhook verification FAILED. mode=%s token=%s", hub_mode, hub_verify_token
    )
    raise HTTPException(status_code=403, detail="Webhook verification failed")


# ---------------------------------------------------------------------------
# POST — incoming comment events
# ---------------------------------------------------------------------------

@router.post("/instagram")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives comment notification events from Meta.

    Flow:
      1. Validate X-Hub-Signature-256 header.
      2. Parse each changed comment from the payload.
      3. Skip if already processed (deduplication).
      4. Check active campaigns for matching post + keyword.
      5. Reply to comment and send DM to commenter.
      6. Mark comment as processed.
    """
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(body, signature):
        logger.error("Invalid webhook signature — rejecting request.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.debug("Webhook payload: %s", json.dumps(payload, indent=2))

    # Retrieve credentials from DB/env
    access_token = _get_config_value(db, "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN")
    ig_account_id = _get_config_value(db, "INSTAGRAM_BUSINESS_ACCOUNT_ID", "INSTAGRAM_BUSINESS_ACCOUNT_ID")

    # Meta wraps events in entry → changes
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue

            value = change.get("value", {})
            comment_id = value.get("id")
            comment_text = value.get("text", "").strip()
            media_id = value.get("media", {}).get("id", "")

            if not comment_id or not comment_text or not media_id:
                logger.debug("Skipping incomplete comment event: %s", value)
                continue

            # --- Deduplication ---
            already_done = (
                db.query(ProcessedComment)
                .filter(ProcessedComment.comment_id == comment_id)
                .first()
            )
            if already_done:
                logger.info("Comment %s already processed — skipping.", comment_id)
                continue

            # --- Find matching active campaigns ---
            campaigns = (
                db.query(Campaign)
                .filter(Campaign.post_id == media_id, Campaign.is_active == True)
                .all()
            )

            matched = False
            for campaign in campaigns:
                keywords = campaign.get_keywords_list()
                comment_lower = comment_text.lower()
                if any(kw in comment_lower for kw in keywords):
                    logger.info(
                        "Keyword match! Comment '%s' → Campaign %d", comment_text, campaign.id
                    )
                    matched = True

                    # 1) Reply to comment
                    try:
                        instagram.reply_to_comment(
                            comment_id,
                            campaign.comment_reply,
                            access_token=access_token,
                        )
                    except Exception as exc:
                        logger.error("Failed to reply to comment %s: %s", comment_id, exc)

                    # 2) Get commenter's IGSID and send DM
                    try:
                        commenter_id = instagram.get_ig_user_id_from_comment(
                            comment_id, access_token=access_token
                        )
                        if commenter_id:
                            instagram.send_dm(
                                commenter_id,
                                campaign.dm_message,
                                access_token=access_token,
                                ig_business_account_id=ig_account_id,
                            )
                        else:
                            logger.warning(
                                "Could not get commenter IGSID for comment %s", comment_id
                            )
                    except Exception as exc:
                        logger.error("Failed to send DM for comment %s: %s", comment_id, exc)

                    break  # One campaign match per comment is enough

            # --- Mark as processed (regardless of match) to avoid reprocessing ---
            if matched or campaigns:
                db.add(ProcessedComment(comment_id=comment_id))
                db.commit()

    # Always return 200 so Meta stops retrying
    return {"status": "ok"}
