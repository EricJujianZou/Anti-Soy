# PRD: Scan Pinned Repos Instead of Most Recent

## Problem
Currently `server/v2/github_resolver.py` fetches repos sorted by `sort=pushed` (most recently pushed). If a user has pinned repos (their showcase projects), those are likely the best candidates for analysis but are currently ignored.

## Implementation

### 1. Add `_fetch_pinned_repos()` helper — `server/v2/github_resolver.py`
- POST to `https://api.github.com/graphql` with query:
  ```graphql
  query($username: String!) {
    user(login: $username) {
      pinnedItems(first: 6, types: REPOSITORY) {
        nodes { ... on Repository { name url } }
      }
    }
  }
  ```
- Requires `GITHUB_TOKEN` (already read at line 21). If no token, return empty list.
- Return list of `{"name": ..., "url": ...}` on success, empty list on any failure.

### 2. Modify `ResolveRepo()` flow
1. After extracting username (line 18), build headers, then call `_fetch_pinned_repos(username, headers)`
2. If pinned repos exist AND `project_names` non-empty: try matching pinned repos first (same fuzzy matching logic as current lines 46-60)
3. If match found in pinned repos, return immediately
4. If no pinned match, fall through to existing REST API logic (current behavior)
5. If `project_names` empty AND pinned repos exist: return first pinned repo instead of most-recently-pushed

**Fallback**: If GraphQL fails (no token, network error, user has no pinned repos), behavior is identical to current code.

## Files to Modify
- `server/v2/github_resolver.py`

## Verification
- Run batch upload for a user with pinned repos. Verify pinned repo is selected over most-recently-pushed.
- Test fallback: user with no pinned repos should still resolve to most-recently-pushed.
- Test fallback: no `GITHUB_TOKEN` set should gracefully skip GraphQL and use REST.
