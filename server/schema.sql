-- SQLite Schema for Anti-Soy Candidate Analysis Platform

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    github_link TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Repositories table
CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    github_link TEXT NOT NULL,
    stars INTEGER DEFAULT 0,
    is_open_source_project INTEGER DEFAULT 0,
    prs_merged INTEGER DEFAULT 0,
    languages TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Repository analysis data table
CREATE TABLE IF NOT EXISTS repo_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL UNIQUE,
    files_organized TEXT,
    test_suites TEXT,
    readme TEXT,
    api_keys TEXT,
    error_handling TEXT,
    comments TEXT,
    print_or_logging TEXT,
    dependencies TEXT,
    commit_density TEXT,
    commit_lines TEXT,
    concurrency TEXT,
    caching TEXT,
    solves_real_problem TEXT,
    aligns_company TEXT,
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
CREATE INDEX IF NOT EXISTS idx_repo_data_repo_id ON repo_data(repo_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
