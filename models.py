"""
SQLAlchemy ORM models for the Instagram Comment-to-DM Automation Tool.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from database import Base


class Config(Base):
    """Stores Instagram API credentials and configuration."""
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Config key={self.key}>"


class Campaign(Base):
    """
    Represents an automation campaign linking a specific Instagram post
    to trigger keywords and automated responses.
    """
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    post_id = Column(String(100), nullable=False, index=True)
    post_caption = Column(Text, nullable=True)
    post_thumbnail_url = Column(Text, nullable=True)
    keywords = Column(Text, nullable=False)          # comma-separated list
    comment_reply = Column(Text, nullable=False)
    dm_message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_keywords_list(self) -> list[str]:
        """Return keywords as a stripped list of lowercase strings."""
        return [kw.strip().lower() for kw in self.keywords.split(",") if kw.strip()]

    def __repr__(self):
        return f"<Campaign id={self.id} post_id={self.post_id} active={self.is_active}>"


class ProcessedComment(Base):
    """
    Tracks which comment IDs have already been processed to prevent
    duplicate replies and DMs from being sent.
    """
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(100), unique=True, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProcessedComment comment_id={self.comment_id}>"
