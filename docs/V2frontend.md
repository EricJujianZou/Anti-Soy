# Anti-Soy V2: Frontend Implementation Plan

## 1. Objective

To redesign the single-repository analysis page to align with the "Interview Weapon" and "Bullshit Detector" product strategy. This plan outlines the frontend components required and the order of implementation based on strategic priority.

## 2. Guiding Principles

- **Top-Down Information:** Present the most critical, decision-making information first. A hiring manager should know within 5 seconds if a candidate is a clear "reject" or potentially "interesting."
- **Evidence over Scores:** De-emphasize abstract scores. Prioritize showing specific code snippets, findings, and actionable "interview weapons."
- **Validate, Don't Describe:** Frame the analysis as a validation of a candidate's claimed skills and project scope (the "bullshit detector").

## 3. Component Implementation Plan (In Order of Priority)

### Step 1: At-a-Glance Signal: Headline & Reject Flag

**Goal:** Create an immediate, top-level signal for the hiring manager.

**Component:** `PageHeader`

**Logic:**
1.  **Check for Reject Flag:** First, check the analysis payload for a high-priority reject signal (e.g., `critical_security_issue: true`).
2.  **Display Reject Banner:** If a reject flag exists, render a prominent **"REJECT"** banner with the specific reason (e.g., "Critical Issue Found: Hardcoded API keys in source code"). The rest of the page can be greyed out or deemphasized.
3.  **Display Standout Headline:** If no reject flag exists, access the `standout_features` object. Combine the `unique_business_demand`, `unique_tech_choices`, and `unique_implementation` fields to generate a catchy summary headline.
    - **Example:** "A real-time pizza delivery tracker built on Elixir and WebSockets." or "Tinder for Horses using Electron and Nix."

### Step 2: The "Bullshit Detector": Business Value Validator

**Goal:** Validate the candidate's project claims against the reality of the codebase.

**Component:** `BusinessValueCard`

**UI:** Title this section clearly, for example: "Project Claim vs. Code Reality" or "Business Value Analysis."

**Content:**
- Display the structured data from the `BusinessValue` model returned by the `/evaluate` endpoint.
- Present `solves_real_problem`, `project_type`, `project_summary`, and `originality_assessment` in a clean, readable format.
- The key is the framing: this section answers the question, "Does the code back up the claims on the resume?"

### Step 3: Critical Issues

**Goal:** Surface any show-stopping errors that warrant immediate rejection but might not have triggered the top-level "Reject" flag.

**Component:** `CriticalIssuesList`

**UI:** A prominent section with a red alert icon, titled "Critical Issues."

**Content:**
- Filter and display all findings where `severity` is `'critical'` from the `bad_practices` analysis.
- Each item should clearly state the issue and provide the file/line number.
- **(Deferrable):** Add the "No Meaningful Error Handling" finding. This will be a single, repo-wide finding triggered if `try/catch` block usage is below 10%. Per our discussion, this can be skipped for the initial MVP if implementation is too complex.

### Step 4: AI Workflow Analysis

**Goal:** Provide insight into *how* the candidate uses AI, focusing on their thought process.

**Component:** `AiUsageAnalysisCard`

**UI:** A section titled "AI-Assisted Workflow Insights."

**Content:**
1.  **AI Instruction Files:** Create a new subsection "AI Development Instructions." If the backend analysis provides a summary of files like `.cursorrules` or `claude.md` (via `standout_features`), display it here. Frame it as "Reveals the candidate's approach to guiding AI in development."
2.  **AI Slop Signals:** Continue to display findings like emoji use or redundant comments, but give them less visual weight than the instruction file analysis.

### Step 5: On-Demand Interview Questions

**Goal:** Gate the detailed interview questions behind a user action to keep the initial view clean.

**Component:** `InterviewQuestions`

**UI:** A button or an expandable section labeled **"Generate Interview Weapons"** or "Show Interview Questions."

**Logic:**
- The interview questions are already pre-fetched and cached from the `/evaluate` API call.
- On click, reveal the list of questions. No new API call is required. This ensures the action is instantaneous for the user.

### Step 6: The Appendix: Detailed Analysis

**Goal:** House all remaining, less-critical data for users who want to perform a deep dive.

**Component:** `DetailedAnalysisTabs`

**UI:** Use a tabbed interface or a series of collapsible accordions at the bottom of the page.

**Content:**
- This section will contain all other metrics:
  - Code Quality scores and findings.
  - Non-critical Bad Practices.
  - Language & Framework breakdown.
  - File tree and other metadata.
