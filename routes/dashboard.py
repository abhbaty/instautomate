"""
Dashboard HTML routes — serves Jinja2 templates for the web UI.

GET /           — Redirect to /dashboard
GET /dashboard  — Main SPA dashboard (settings + campaigns)
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])

templates = Jinja2Templates(directory="templates")


@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
