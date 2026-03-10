# Cross Reference Layer: Resume Project to GitHub Repo Matching

## Overview

Improvement to github parsing from resume workflow. Intends to feed into current @github_resolver.py and related services. The resolver doesn't work properly right now because there is no list of project names supplied. For my testing it's jumping between 2 different repos. We need to upgrade it.

This module acts as a **filtering layer before git cloning**. Given a single candidate's GitHub profile URL and their parsed resume text, it identifies which of their public repositories correspond to projects claimed on their resume. The output is a structured person object containing matched and unmatched projects, so downstream systems only clone repos that matter.

## Input

A single candidate object:

```json
{
  "name": "John Smith",
  "github": "github.com/johnsmith",
  "pages": [1, 2],
  "confidence": "high",
  "resume_text": "<full extracted text from resume>"
}
```

The `github_url` field should be bulletproofed to handle any of these formats:
  - `https://github.com/username`
  - `github.com/username`
  - `https://github.com/username/` (trailing slash)

EXISTING FUNCTION: 
Extract the username by stripping protocol, domain, and trailing slashes. Validate that the extracted username matches the pattern `[a-zA-Z0-9\-]+`.

## Output

A person object:

```json
{
  "github_username": "someuser",
  "github_url": "https://github.com/someuser",
  "resume_projects": [
    {
      "name": "ChatApp",
      "description": "Real time messaging platform with WebSocket support",
      "tech_stack": ["React", "Node.js", "Socket.io", "MongoDB"]
    }
  ],
  "matched_projects": [
    {
      "resume_project_name": "ChatApp",
      "repo_name": "chat-app-v2",
      "repo_url": "https://github.com/someuser/chat-app-v2",
      "confidence": 0.91,
      "match_signals": {
        "name_similarity": 0.85,
        "description_similarity": 0.92,
        "tech_stack_overlap": 0.75
      }
    }
  ],
  "unmatched_projects": [
    {
      "name": "Arduino Robot Arm",
      "description": "6DOF robotic arm with computer vision",
      "tech_stack": ["C++", "OpenCV", "Arduino"],
      "reason": "no_matching_repo_found"
    }
  ],
  "match_summary": "1/2 verified",
  "repos_to_clone": ["chat-app-v2"]
}
```

### Notes on output

  - `unmatched_projects` are informational only. No penalty. Candidates may have private repos, hardware projects, or work under NDA.
  - `repos_to_clone` is the filtered list of repo names that downstream cloning should act on.
  - `confidence` is a float between 0 and 1. Only repos above a configurable threshold (default 0.6) should appear in `matched_projects`.

## Architecture

### Step 1: Extract GitHub Username

Parse the `github_url` input. Strip protocol, strip `github.com/`, strip trailing slashes. Validate the remaining string is a valid GitHub username. If parsing fails, return an error object with `"error": "invalid_github_url"`.

### Step 2: Fetch All Public Repo Metadata

Hit the GitHub API:

```
GET https://api.github.com/users/{username}/repos?per_page=100&type=owner
```

Use the GitHub PAT in the `Authorization: Bearer {token}` header for 5000 req/hr rate limit.

For each repo, extract and store:
  - `name`
  - `description`
  - `language` (primary language)
  - `languages_url` (for fetching full language breakdown if needed)
  - `stargazers_count`
  - `fork` (indicate parent repo for fork verification later)
  - `created_at`
  - `updated_at`
  - `html_url`
  - `topics` (repo tags if set)


If the user has more than 100 repos, paginate using the `Link` header. In practice this is rare.

### Step 3: Extract Resume Projects via LLM + Description matching (see step 4, signal 2, below)

Send the resume text to Gemini Flash with this prompt:

```
You are given a candidate's resume text and a list of their public GitHub repositories.

Do two things:

1. Extract all projects from the resume. For each project, return the name exactly as written, a one sentence description based on the resume, and a list of technologies/languages/frameworks mentioned.

2. For each extracted project, compare it against the provided GitHub repos. If a repo likely refers to the same project, match them and give a confidence score from 0.0 to 1.0 based on name similarity, description similarity, and tech stack overlap. If no repo matches, leave matched_repo as null.

Return ONLY valid JSON. No preamble. No markdown. Format:

{
  "projects": [
    {
      "name": "...",
      "description": "...",
      "tech_stack": ["...", "..."],
      "matched_repo": {
        "repo_name": "...",
        "confidence": 0.0,
        "match_signals": {
          "name_similarity": 0.0,
          "description_similarity": 0.0,
          "tech_stack_overlap": 0.0
        }
      }
    }
  ]
}

If no match is found for a project, set matched_repo to null.
If no projects are found in the resume, return: {"projects": []}
Each repo should match to at most one project. If two projects could match the same repo, assign it to the stronger match.

Resume:
{resume_text}

GitHub Repos:
{repo_list_json}
```

Parse the response. If JSON parsing fails, retry once. If it fails again, flag the candidate with `"error": "resume_parse_failed"`.

### Step 4: Match Resume Projects to Repos

If a project appears on the resume, but it's a forked project:
Fork validation: Ensure that the forked repo has contributions by the user, and not just forking something to fake a good profile
So the fork validation logic simplifies to:

Is this repo a fork? Check fork: true from the repos endpoint.
If yes, grab the parent field (gives you the parent repo's owner/name).
Hit GET /repos/{parent_owner}/{parent_repo}/commits?author={username}
If commits exist (more than 1): legit contributor, treat it like an owned repo for cross referencing.
If zero commits: skip this repo for anlaysis, flag the fact that this is a forked repo and the user only made x number of commits on it

For each resume project, score it against every repo using three signals:

**Signal 1: Name Similarity**

Compute a normalized similarity score between the resume project name and the repo name. Use a combination of:
  - Lowercase both strings
  - Strip common separators (spaces, underscores) and compare
  - Token overlap (split both into words, compute Jaccard similarity)
  - Levenshtein ratio as a fallback

Weight: 0.4

Example: "ChatApp" vs "chat-app-v2" should score high because token overlap on ["chat", "app"] is strong.

**Signal 2: Description Similarity**

Compare the resume project description against the repo's GitHub description. If the repo has no description, this signal scores 0 and its weight is redistributed to the other signals.

Use the same LLM call (Gemini Flash) as the one before to extract resume text use for semantic comparison:

refer back to the combined prompt above.

Weight: 0.35

**Signal 3: Tech Stack Overlap**

Compare the resume project's tech_stack list against the repo's `language` field and `topics`. If needed, hit the `languages_url` endpoint for the full language breakdown.

Normalize language names (e.g., "JavaScript" and "JS" should match, "Node.js" and "node" should match). Compute overlap as:

```
overlap = len(intersection) / len(resume_tech_stack)
```

Weight: 0.25

**Combined Score:**

```
confidence = (name_weight * name_score) + (desc_weight * desc_score) + (tech_weight * tech_score)
```

If repo description is null, redistribute:
```
confidence = (0.55 * name_score) + (0.45 * tech_score)
```

**Matching rules:**
  - If confidence >= 0.6, it's a match. Add to `matched_projects`.
  - Each resume project matches to at most one repo (the highest scoring one).
  - Each repo can match to at most one resume project.
  - Resolve conflicts greedily: if two resume projects match the same repo, the higher confidence one wins. The losing project goes to `unmatched_projects`.

### Step 5: Assemble Output

Build the person object as defined in the Output section above. The `repos_to_clone` list is simply the repo names from `matched_projects`.

## Concurrency Model for Batch Processing

When processing a batch of candidates (e.g., from the PDF intake layer, not built yet), this module should be called concurrently.

```python
import asyncio

semaphore = asyncio.Semaphore(15)

async def process_candidate(candidate):
    async with semaphore:
        return await cross_reference(candidate)

results = await asyncio.gather(*[
    process_candidate(c) for c in candidates
])
```

The semaphore caps concurrency at 15 to stay well within GitHub API rate limits (5000/hr with PAT). Each candidate requires:
  - 1 GitHub API call for repos
  - 1 LLM call for resume project extraction and description matching

For a typical candidate with 4 resume projects and 10 repos, this is roughly 1 API call + 5 LLM calls. At 15 concurrent workers, 100 candidates should complete in under 2 minutes.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid GitHub URL | Return error object, skip candidate |
| GitHub user not found (404) | Return error object, skip candidate |
| GitHub rate limit hit (403) | Exponential backoff, retry up to 3 times |
| LLM returns invalid JSON | Retry once, then flag candidate |
| Forked project mentioned in resume but no commits done by user to parent |flag|
| No resume projects extracted | Return person object with empty arrays, flag |
| No repos found for user | Return person object with all projects unmatched |

## Configuration

These should be environment variables or a config object:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GITHUB_PAT` | required | GitHub Personal Access Token |
| `MATCH_CONFIDENCE_THRESHOLD` | 0.6 | Minimum score to count as a match |
| `MAX_CONCURRENT_WORKERS` | 15 | Semaphore limit for batch processing |
| `LLM_MODEL` | gemini-2.0-flash | Model for project extraction and description matching |
| `NAME_WEIGHT` | 0.4 | Weight for name similarity signal |
| `DESC_WEIGHT` | 0.35 | Weight for description similarity signal |
| `TECH_WEIGHT` | 0.25 | Weight for tech stack overlap signal |

## File Structure

```
cross_reference/
    __init__.py
    main.py              # Entry point: cross_reference(candidate) -> PersonObject
    github_client.py     # GitHub API interactions
    resume_parser.py     # LLM based project extraction
    matcher.py           # Scoring and matching logic
    models.py            # Pydantic models for Person, Project, MatchResult
    config.py            # Configuration and env vars
    utils.py             # URL parsing, string normalization, language aliases
```

## Dependencies

  - `httpx` (async HTTP client for GitHub API and LLM calls)
  - `python-Levenshtein` (fast string similarity)
  - `pydantic` (data validation and output models)
  - `google-generativeai` or equivalent SDK for Gemini Flash calls

## Testing Notes

For the coding agent implementing this:
  - Write unit tests for URL parsing edge cases (all formats listed above)
  - Write unit tests for name matching ("ChatApp" vs "chat-app-v2", "My Project" vs "myproject")
  - Write unit tests for tech stack normalization ("JavaScript" == "JS", "Node.js" == "node")
  - Mock GitHub API responses for integration tests
  - Use a sample resume text fixture for LLM extraction tests
  - Test the greedy conflict resolution (two projects matching same repo)
