---
title: Instaautomate
emoji: 🤖
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 4.36.0
app_file: app.py
pinned: false
---

# 🤖 InstaAutomate — Instagram Comment-to-DM Automation Tool

> **ManyChat-style automation using the official Meta Graph API.**
> When someone comments a keyword on your Instagram post, the tool automatically:
> 1. Replies to the comment publicly
> 2. Sends the commenter a private DM

---

## 📋 Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Instagram API Setup (Step-by-Step)](#instagram-api-setup)
4. [Local Development](#local-development)
5. [Environment Variables](#environment-variables)
6. [Deployment](#deployment)
   - [Railway](#railway)
   - [Render](#render)
   - [Docker](#docker)
7. [API Reference](#api-reference)
8. [FAQ & Troubleshooting](#faq--troubleshooting)

---

## Features

- ✅ **Webhook receiver** — real-time Instagram comment events via Meta Graph API
- ✅ **Keyword matching** — case-insensitive, partial-match, comma-separated keywords
- ✅ **Auto comment reply** — public reply posted under the matching comment
- ✅ **Auto DM** — private direct message sent to the commenter
- ✅ **Deduplication** — each comment is only processed once
- ✅ **Campaign management** — multiple automations for different posts
- ✅ **Web dashboard** — manage campaigns and credentials in your browser
- ✅ **Webhook signature verification** — validates X-Hub-Signature-256 header
- ✅ **Rate-limit handling** — exponential back-off on 429/5xx errors
- ✅ **Cloud-ready** — Dockerfile, Railway, and Render configs included

---

## Architecture

```
POST /webhook/instagram
        │
        ▼
  Verify X-Hub-Signature-256
        │
        ▼
  Parse comment event
        │
        ▼
  Check: already processed?  ──YES──▶  skip
        │ NO
        ▼
  Find active campaigns matching post_id
        │
        ▼
  Keyword match?  ──NO──▶  skip
        │ YES
        ▼
  reply_to_comment()  +  send_dm()
        │
        ▼
  Mark comment as processed (DB)
```

**Tech Stack:**
| Layer | Tech |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Database | SQLite (SQLAlchemy ORM) |
| Frontend | Vanilla HTML + CSS + JS |
| Templates | Jinja2 |
| Deployment | Docker / Railway / Render |

---

## Instagram API Setup

> **Complete step-by-step guide for users who don't have a Facebook Developer App yet.**

### Step 1 — Convert Instagram Account to Business/Creator

1. Open the Instagram mobile app.
2. Go to **Settings → Account → Switch to Professional Account**.
3. Choose **Business** or **Creator**.
4. This is required to access the Instagram Graph API.

---

### Step 2 — Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com) and log in with your Facebook account.
2. Click **My Apps → Create App**.
3. Choose **Other** → **Next**.
4. Select **Business** as the app type → **Next**.
5. Enter an App Name (e.g. `InstaAutomate`) and your contact email.
6. Click **Create App**.

---

### Step 3 — Add Instagram Graph API Product

1. In your new app's dashboard, click **Add Product**.
2. Find **Instagram Graph API** and click **Set Up**.
3. Also add **Webhooks** (click **Set Up** next to it).

---

### Step 4 — Connect Your Instagram Business Account

1. In the left menu: **Instagram Graph API → Settings**.
2. Under **Instagram Testers**, add your Instagram account username.
3. Go to your Instagram account → **Settings → Apps and Websites** → accept the tester invite.
4. In the developer app: go to **Instagram Graph API → Basic Display → Add Instagram Test User** — add your account here too if prompted.

---

### Step 5 — Get Required Permissions

Your app needs these permissions:
- `instagram_manage_comments` — to post comment replies
- `instagram_manage_messages` — to send DMs ⚠️ (requires App Review)
- `pages_show_list` — to list connected Pages
- `instagram_basic` — basic profile access

During **development**, you can use your own account without App Review.
For **production** (other users), submit for App Review.

---

### Step 6 — Generate a Long-Lived User Access Token

#### 6a. Get a Short-Lived Token

1. Go to [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer).
2. Select your App from the top-right dropdown.
3. Click **Generate Access Token** and grant all the required permissions.
4. Copy the token — it's valid for **1 hour**.

#### 6b. Exchange for a Long-Lived Token (valid 60 days)

Open your browser or use curl:

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
```

You'll get a response like:
```json
{
  "access_token": "EAAxxxLONG_LIVED_TOKEN",
  "token_type": "bearer",
  "expires_in": 5183944
}
```

Copy the `access_token` value.

#### 6c. Refreshing the Token (before 60 days expire)

Long-lived tokens **reset** their 60-day timer when refreshed. Run this anytime:

```bash
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=CURRENT_LONG_LIVED_TOKEN"
```

> **Tip:** Set a monthly calendar reminder to refresh your token.

---

### Step 7 — Get Your Instagram Business Account ID

```bash
curl "https://graph.facebook.com/v19.0/me/accounts?access_token=YOUR_LONG_LIVED_TOKEN"
```

Look for your Page in the response. Then:

```bash
curl "https://graph.facebook.com/v19.0/YOUR_PAGE_ID?fields=instagram_business_account&access_token=YOUR_LONG_LIVED_TOKEN"
```

The `instagram_business_account.id` is your `INSTAGRAM_BUSINESS_ACCOUNT_ID`.

---

### Step 8 — Get a Post ID for a Specific Instagram Post

Use the Graph API Explorer or curl:

```bash
curl "https://graph.facebook.com/v19.0/YOUR_IG_ACCOUNT_ID/media?fields=id,caption,media_type,permalink&access_token=YOUR_LONG_LIVED_TOKEN"
```

Each media object has an `id` field — this is your **Post ID** to use in campaigns.

---

### Step 9 — Configure the Webhook

1. In your Meta Developer App: **Webhooks → Add Subscription**.
2. Select **Instagram** as the object.
3. Enter your **Callback URL**:
   ```
   https://your-deployed-domain.com/webhook/instagram
   ```
4. Enter your **Verify Token** — this is the value you set for `WEBHOOK_VERIFY_TOKEN` in your `.env`.
5. Click **Verify and Save**.
6. After verification succeeds, click **Add Subscriptions**.
7. Subscribe to the **comments** field.

> **Local testing tip:** Use [ngrok](https://ngrok.com) to expose your local server:
> ```bash
> ngrok http 8000
> # Then use the https://xxxxx.ngrok.io URL as your callback
> ```

---

## Local Development

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-username/instautomate.git
cd instautomate

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your actual credentials

# 5. Run the server
uvicorn main:app --reload --port 8000
```

Open your browser at: **http://localhost:8000/dashboard**

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | ✅ | Long-lived User Access Token (60 days) |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | ✅ | Numeric ID of your IG Business Account |
| `FACEBOOK_APP_SECRET` | ✅ | App Secret from Meta Developer dashboard |
| `WEBHOOK_VERIFY_TOKEN` | ✅ | Secret string for webhook verification |
| `DATABASE_URL` | ✅ | SQLite: `sqlite:///./app.db` or a Postgres URL |
| `PORT` | Optional | HTTP port (default: 8000, Railway sets automatically) |

All variables can also be set via the web dashboard (**Settings** page) — they take precedence.

---

## Deployment

### Railway

1. Push your code to a GitHub repository.
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**.
3. Select your repository.
4. Railway detects the `railway.toml` and builds automatically.
5. In **Variables**, add all environment variables from `.env.example`.
6. Railway provides a public HTTPS URL — use it as your webhook callback URL.

```
https://your-app.up.railway.app/webhook/instagram
```

### Render

1. Push to GitHub.
2. Go to [render.com](https://render.com) → **New → Web Service**.
3. Connect your GitHub repo.
4. Render detects `render.yaml` automatically.
5. Add environment variables in the Render dashboard.

### Docker

```bash
# Build the image
docker build -t instautomate .

# Run with your .env file
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/data instautomate
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns `{"status":"ok"}` |
| `GET` | `/dashboard` | Web dashboard UI |
| `GET` | `/webhook/instagram` | Facebook webhook challenge verification |
| `POST` | `/webhook/instagram` | Receive Instagram comment events |
| `GET` | `/api/campaigns` | List all campaigns |
| `POST` | `/api/campaigns` | Create a campaign |
| `GET` | `/api/campaigns/{id}` | Get a single campaign |
| `PUT` | `/api/campaigns/{id}` | Update a campaign |
| `DELETE` | `/api/campaigns/{id}` | Delete a campaign |
| `PATCH` | `/api/campaigns/{id}/toggle` | Toggle active/inactive |
| `GET` | `/api/config` | Get saved config (tokens masked) |
| `POST` | `/api/config` | Set a config key |
| `GET` | `/api/post-preview?post_id=…` | Fetch post thumbnail + caption |
| `GET` | `/api/stats` | Dashboard stats |
| `GET` | `/docs` | Swagger UI |

---

## ⚠️ DM Limitation — Important

The Instagram Graph API has strict rules for sending Direct Messages:

> **The business can only DM a user if the user has previously messaged the business account first**, OR the app has the `instagram_manage_messages` permission with an approved business use case.

**To apply for `instagram_manage_messages` for DM automation:**
1. Go to your Meta Developer App → **App Review → Permissions and Features**.
2. Click **Request** next to `instagram_manage_messages`.
3. Provide a detailed description of your use case, a screencast demo, and data handling policy.
4. Meta reviews within a few days to weeks.

**In the meantime:** Comment replies work immediately without App Review!

---

## FAQ & Troubleshooting

**Q: The webhook verification failed / 403 error on setup?**
- Ensure `WEBHOOK_VERIFY_TOKEN` in your `.env` exactly matches what you entered in the Meta webhook panel.

**Q: Comments are not triggering the automation?**
- Make sure the campaign `post_id` is the numeric ID (not a permalink).
- Ensure the campaign is set to **Active**.
- Check that the webhook subscription includes the `comments` field.
- Check the server logs (`uvicorn` output).

**Q: I'm getting API errors for DMs?**
- Check that the commenter has messaged your business before, OR that you have the `instagram_manage_messages` permission approved.

**Q: My access token expired?**
- Refresh it using the curl command in [Step 6c](#6c-refreshing-the-token-before-60-days-expire).
- Update it in the Settings page or your `.env`.

**Q: Can I migrate from SQLite to PostgreSQL?**
- Yes! Change `DATABASE_URL` in `.env` to a PostgreSQL connection string.
- The SQLAlchemy ORM works identically with both databases.
- On Railway, provision a Postgres plugin and copy the `DATABASE_URL` it provides.
