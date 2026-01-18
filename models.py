"""
SQLAlchemy models for Anti-Soy Candidate Analysis Platform
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model representing a GitHub user"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    github_link = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to repos
    repos = relationship("Repo", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Repo(Base):
    """Repository model representing a GitHub repository"""
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    github_link = Column(String, nullable=False)
    stars = Column(Integer, default=0)
    is_open_source_project = Column(Boolean, default=False)
    prs_merged = Column(Integer, default=0)
    languages = Column(Text)  # JSON stored as TEXT

    # Relationships
    user = relationship("User", back_populates="repos")
    repo_data = relationship("RepoData", back_populates="repo", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Repo(id={self.id}, github_link='{self.github_link}', stars={self.stars})>"


class RepoData(Base):
    """Repository analysis data model storing detailed metrics"""
    __tablename__ = "repo_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # JSON fields for analysis metrics
    files_organized = Column(JSON)
    test_suites = Column(JSON)
    readme = Column(JSON)
    api_keys = Column(JSON)
    error_handling = Column(JSON)
    comments = Column(JSON)
    print_or_logging = Column(JSON)
    dependencies = Column(JSON)
    commit_density = Column(JSON)
    commit_lines = Column(JSON)
    concurrency = Column(JSON)
    caching = Column(JSON)
    solves_real_problem = Column(JSON)
    aligns_company = Column(JSON)

    # Relationship
    repo = relationship("Repo", back_populates="repo_data")

    def __repr__(self):
        return f"<RepoData(id={self.id}, repo_id={self.repo_id})>"
