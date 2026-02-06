-- SQLite Schema for Anti-Soy Candidate Analysis Platform (V2)

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    github_link TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Repositories table
CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    github_link TEXT NOT NULL UNIQUE,
    repo_name TEXT NOT NULL,
    stars INTEGER DEFAULT 0,
    languages TEXT,  -- JSON: {language: bytes}
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Repository analysis data table (V2)
CREATE TABLE IF NOT EXISTS repo_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL UNIQUE,
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Verdict
    verdict_type TEXT,  -- "Slop Coder", "Junior", "Senior", "Good Use of AI"
    verdict_confidence INTEGER,  -- 0-100
    
    -- AI Slop Analyzer
    ai_slop_score INTEGER,  -- 0-100
    ai_slop_confidence TEXT,  -- "low", "medium", "high"
    ai_slop_data TEXT,  -- JSON: Full AISlop object
    
    -- Bad Practices Analyzer
    bad_practices_score INTEGER,  -- 0-100
    bad_practices_data TEXT,  -- JSON: Full BadPractices object
    
    -- Code Quality Analyzer
    code_quality_score INTEGER,  -- 0-100
    code_quality_data TEXT,  -- JSON: Full CodeQuality object
    
    -- Files Analyzed
    files_analyzed TEXT,  -- JSON: List of FileAnalyzed objects
    
    -- Interview Questions (generated on demand)
    interview_questions TEXT,  -- JSON: List of InterviewQuestion objects
    
    FOREIGN KEY (repo_id) REFERENCES repos(id) ON DELETE CASCADE
);

-- Trigger to update updated_at timestamp on users table
CREATE TRIGGER IF NOT EXISTS update_users_timestamp 
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_repos_user_id ON repos(user_id);
CREATE INDEX IF NOT EXISTS idx_repos_github_link ON repos(github_link);
CREATE INDEX IF NOT EXISTS idx_repo_data_repo_id ON repo_data(repo_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
