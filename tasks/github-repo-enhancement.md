REQ-002: Backend — Resume Enhancement & GitHub Repo Resolver

  Branch: feat/resume-enhancement
  Can start: Immediately — no dependencies
  Files owned: server/v2/resume_parser.py, server/v2/github_resolver.py (new file)

  ---
  Overview

  Two additions to the resume processing pipeline:
  1. Extract candidate name, university, and project names from resume plaintext
  2. New module that resolves a GitHub profile + project name list → a single best-matching repo URL

  ---
  Part 1: resume_parser.py additions

  New dataclass CandidateInfo:
  class CandidateInfo:
      name: str              # first non-empty line of plaintext
      university: str | None # regex match, None if not found
      github_profile_url: str | None  # from existing GithubFromResumeDump, None if raises
      project_names: list[str]        # extracted from Projects section, may be empty

  New function ExtractCandidateInfo(resume_dump: struct_resume_dump) -> CandidateInfo:

  - Name: first non-empty, non-whitespace line of resume_dump.plaintext
  - University: regex scan of full plaintext for patterns:
    - "University of \w+", "\w+ University", "\w+ College", "\w+ Institute of Technology", "MIT", "ETH", common acronyms
    - Return the first match found, None if no match
  - GitHub profile URL: call existing GithubFromResumeDump(resume_dump), wrap in try/except ResumeParseException → return None on failure       
  - Project names: scan plaintext for a section header matching "project" (case-insensitive). Once found, extract the subsequent lines that     
  appear to be project titles (short lines, ≤6 words, not all lowercase, before the next section header). Return empty list if no Projects      
  section found.

  ---
  Part 2: github_resolver.py (new file)

  ResolveRepo(github_profile_url: str, project_names: list[str]) -> str

  Steps:
  1. Extract username from the profile URL
  2. Call GitHub API: GET https://api.github.com/users/{username}/repos?sort=pushed&per_page=100
    - Include Authorization: Bearer {GITHUB_TOKEN} header from env
  3. If API call fails or returns non-200: raise ResumeParseException("GitHub API error: ...")
  4. If response returns 0 public repos: raise ResumeParseException("No public repositories found for this user.")
  5. Matching logic (only if project_names is non-empty):
    - For each repo, compute a match score against all project names
    - Score = 1 if the repo name (hyphens/underscores → spaces, lowercased) is a substring of any project name (lowercased), or vice versa.     
  Otherwise 0.
    - Pick the repo with the highest score
  6. Fallback (if project_names is empty or all scores = 0): return the first repo in the API response (most recently pushed, since sorted by   
  pushed)
  7. Return "https://github.com/{username}/{repo_name}"

  ---
  Acceptance Criteria

  - ExtractCandidateInfo returns correct name from a standard PDF resume
  - University extraction returns None for resumes with non-standard school names (does not crash)
  - ResolveRepo correctly prefers a repo whose name matches a project name from the resume
  - ResolveRepo falls back to most recent repo when no project name matches
  - All GitHub API calls include the auth token
