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
    repo_analysis = relationship("RepoAnalysis", back_populates="repo", uselist=False, cascade="all, delete-orphan")
    repo_evaluation = relationship("RepoEvaluation", back_populates="repo", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Repo(id={self.id}, github_link='{self.github_link}', stars={self.stars})>"


class RepoAnalysis(Base):
    """Repository analysis data (owned by /analyze endpoint)"""
    __tablename__ = "repo_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False, unique=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Verdict
    verdict_type = Column(String, nullable=False)  # "Slop Coder", "Junior", "Senior", "Good AI Coder"
    verdict_confidence = Column(Integer, nullable=False)  # 0-100

    # AI Slop Analyzer
    ai_slop_score = Column(Integer, nullable=False)  # 0-100
    ai_slop_confidence = Column(String, nullable=False)  # "low", "medium", "high"
    ai_slop_data = Column(Text, nullable=False)  # JSON: Full AISlop object

    # Bad Practices Analyzer
    bad_practices_score = Column(Integer, nullable=False)  # 0-100
    bad_practices_data = Column(Text, nullable=False)  # JSON: Full BadPractices object

    # Code Quality Analyzer
    code_quality_score = Column(Integer, nullable=False)  # 0-100
    code_quality_data = Column(Text, nullable=False)  # JSON: Full CodeQuality object

    # Files Analyzed
    files_analyzed = Column(Text, nullable=False)  # JSON: List of FileAnalyzed objects

    # Relationship
    repo = relationship("Repo", back_populates="repo_analysis")

    def __repr__(self):
        return f"<RepoAnalysis(id={self.id}, repo_id={self.repo_id}, verdict='{self.verdict_type}')>"


class RepoEvaluation(Base):
    """Repository evaluation data (owned by /evaluate endpoint)"""
    __tablename__ = "repo_evaluation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repos.id", ondelete="CASCADE"), nullable=False, unique=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Rejection Status
    is_rejected = Column(Integer, default=0, nullable=False)  # SQLite boolean (0 or 1)
    rejection_reason = Column(Text)  # Nullable

    # Business Value (JSON)
    business_value = Column(Text, nullable=False)  # JSON: BusinessValue object

    # Standout Features (JSON array of strings)
    standout_features = Column(Text, nullable=False)  # JSON: List of strings

    # Interview Questions (JSON)
    interview_questions = Column(Text, nullable=False)  # JSON: List of InterviewQuestion objects

    # Relationship
    repo = relationship("Repo", back_populates="repo_evaluation")

    def __repr__(self):
        return f"<RepoEvaluation(id={self.id}, repo_id={self.repo_id}, rejected={bool(self.is_rejected)})>"
