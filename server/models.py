"""
SQLAlchemy models for Anti-Soy Candidate Analysis Platform (V2)
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model representing a GitHub user"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
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
    github_link = Column(String, nullable=False, unique=True)
    repo_name = Column(String, nullable=False)
    stars = Column(Integer, default=0)
    languages = Column(Text)  # JSON stored as TEXT

    # Relationships
    user = relationship("User", back_populates="repos")
    repo_data = relationship("RepoData", back_populates="repo", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Repo(id={self.id}, github_link='{self.github_link}', stars={self.stars})>"


class RepoData(Base):
    """Repository analysis data model (V2) storing analyzer results"""
    __tablename__ = "repo_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False, unique=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Verdict
    verdict_type = Column(String)  # "Slop Coder", "Junior", "Senior", "Good Use of AI"
    verdict_confidence = Column(Integer)  # 0-100
    
    # AI Slop Analyzer
    ai_slop_score = Column(Integer)  # 0-100
    ai_slop_confidence = Column(String)  # "low", "medium", "high"
    ai_slop_data = Column(Text)  # JSON: Full AISlop object
    
    # Bad Practices Analyzer
    bad_practices_score = Column(Integer)  # 0-100
    bad_practices_data = Column(Text)  # JSON: Full BadPractices object
    
    # Code Quality Analyzer
    code_quality_score = Column(Integer)  # 0-100
    code_quality_data = Column(Text)  # JSON: Full CodeQuality object
    
    # Files Analyzed
    files_analyzed = Column(Text)  # JSON: List of FileAnalyzed objects
    
    # Interview Questions (generated on demand)
    interview_questions = Column(Text)  # JSON: List of InterviewQuestion objects

    # Relationship
    repo = relationship("Repo", back_populates="repo_data")

    def __repr__(self):
        return f"<RepoData(id={self.id}, repo_id={self.repo_id}, verdict='{self.verdict_type}')>"
