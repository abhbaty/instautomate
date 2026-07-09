"""
Instagram Graph API client.

Handles all outbound calls to Meta's Graph API:
  - reply_to_comment(comment_id, message)
  - send_dm(instagram_user_id, message)
  - get_post_details(post_id)

All requests use exponential back-off on rate-limit (HTTP 429) or transient
server errors (HTTP 5xx).  Responses are logged at DEBUG level; errors are
logged at ERROR level.
"""

import os
import time
import logging
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_token() -> str:
    """Return the current access token from the environment.
    The token can be overridden at runtime via the database Config table —
    callers that need the DB value should pass it explicitly."""
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    return token


def _request(
    method: str,
    url: str,
    *,
    access_token: Optional[str] = None,
    max_retries: int = 3,
    **kwargs,
) -> dict:
    """
    Make an HTTP request to the Graph API with automatic retry and back-off.

    :param method: HTTP method ('GET', 'POST', etc.)
    :param url:    Full URL to call
    :param access_token: Override for the default token
    :param max_retries:  How many times to retry on 429 / 5xx
    :param kwargs: Additional arguments forwarded to requests.request()
    :returns: Parsed JSON response dict
    :raises: RuntimeError on unrecoverable error
    """
    token = access_token or _get_token()
    params = kwargs.pop("params", {})
    params["access_token"] = token

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, params=params, timeout=15, **kwargs)
            logger.debug(
                "%s %s → %s | body: %s",
                method,
                url,
                response.status_code,
                response.text[:500],
            )

            if response.status_code == 429 or response.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(
                    "Rate-limit / server error (attempt %d/%d). Retrying in %ds…",
                    attempt,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except requests.RequestException as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.error(
                "Request error (attempt %d/%d): %s. Retrying in %ds…",
                attempt,
                max_retries,
                exc,
                wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"All {max_retries} attempts failed for {method} {url}. Last error: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reply_to_comment(
    comment_id: str, message: str, access_token: Optional[str] = None
) -> dict:
    """
    Post a public reply to an Instagram comment.

    :param comment_id: The ID of the comment to reply to
    :param message:    Text of the reply
    :param access_token: Override token (uses env var if omitted)
    :returns: Graph API response dict (contains 'id' of the new comment)
    """
    url = f"{GRAPH_API_BASE}/{comment_id}/replies"
    logger.info("Replying to comment %s", comment_id)
    result = _request("POST", url, access_token=access_token, json={"message": message})
    logger.info("Reply posted — new comment id: %s", result.get("id"))
    return result


def send_dm(
    instagram_user_id: str, message: str, access_token: Optional[str] = None,
    ig_business_account_id: Optional[str] = None,
) -> dict:
    """
    Send a private Direct Message to an Instagram user.

    ⚠️  The Graph API only allows businesses to message users who have
    previously messaged the account OR who have opted in.  The
    instagram_manage_messages permission (with approved use case) is
    required.  See README for details.

    :param instagram_user_id: IGSID of the recipient
    :param message: Text of the DM
    :param access_token: Override token
    :param ig_business_account_id: The IG Business Account ID (sender)
    :returns: Graph API response dict
    """
    account_id = ig_business_account_id or os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    url = f"{GRAPH_API_BASE}/{account_id}/messages"
    payload = {
        "recipient": {"id": instagram_user_id},
        "message": {"text": message},
    }
    logger.info("Sending DM to user %s", instagram_user_id)
    result = _request("POST", url, access_token=access_token, json=payload)
    logger.info("DM sent — response: %s", result)
    return result


def get_post_details(post_id: str, access_token: Optional[str] = None) -> dict:
    """
    Fetch metadata for an Instagram media object (post/reel/video).

    :param post_id: The Instagram media ID
    :param access_token: Override token
    :returns: Dict with keys: id, caption, thumbnail_url, media_type, permalink
    """
    url = f"{GRAPH_API_BASE}/{post_id}"
    fields = "id,caption,thumbnail_url,media_url,media_type,permalink"
    logger.info("Fetching post details for %s", post_id)
    result = _request("GET", url, access_token=access_token, params={"fields": fields})

    # Normalise: prefer thumbnail_url (videos), fall back to media_url (images)
    result.setdefault("thumbnail_url", result.get("media_url", ""))
    result.setdefault("caption", "")
    return result


def get_ig_user_id_from_comment(comment_id: str, access_token: Optional[str] = None) -> Optional[str]:
    """
    Retrieve the IGSID (Instagram Scoped User ID) of the user who posted
    a given comment.  This ID is needed for send_dm().

    :param comment_id: Graph API comment ID
    :param access_token: Override token
    :returns: IGSID string or None if not available
    """
    url = f"{GRAPH_API_BASE}/{comment_id}"
    fields = "id,from"
    try:
        result = _request("GET", url, access_token=access_token, params={"fields": fields})
        from_data = result.get("from", {})
        return from_data.get("id")
    except Exception as exc:
        logger.error("Could not retrieve user ID for comment %s: %s", comment_id, exc)
        return None
