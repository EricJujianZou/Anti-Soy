# Anti-Soy: Product Vision

Product and business documentation for the Anti-Soy candidate analysis platform.

---

## Table of Contents

1. [Problem Space](#problem-space)
2. [Market Analysis](#market-analysis)
3. [Solution Overview](#solution-overview)
4. [Discovery vs. Analysis Strategy](#discovery-vs-analysis-strategy)
5. [Vibe Coder Detection Metrics](#vibe-coder-detection-metrics)
6. [Use Cases](#use-cases)
7. [Edge Cases](#edge-cases)
8. [Privacy & Ethics](#privacy--ethics)
9. [Roadmap](#roadmap)

---

## Problem Space

### The Hiring Paradox

**For Startups:**

- Early-stage startups lack dedicated HR teams
- Founders' time is extremely valuable (runway is limited)
- Need to hire competent engineers but can't afford extensive vetting processes
- Risk of bad hires is catastrophic at small scale
- Current process: 30-second GitHub glance → "tell me about your project" in interviews (without actually reviewing code)

**For Candidates:**

- Competent developers without large online presence go unnoticed
- AI-assisted development has made it easier to create "pretty" projects with shallow substance
- Hard to differentiate genuine engineering skill from surface-level contributions

### Core Issues with Technical Hiring

1. **Resume Misrepresentation**: Candidates exaggerate skills, list technologies they've barely touched
2. **AI Dependency**: Growing number of developers over-rely on AI (Claude, GitHub Copilot) without understanding fundamentals
3. **Vibe Coding**: Code that looks good superficially but lacks proper error handling, security, scalability
4. **Unknown Talent**: Great engineers working in private repos or without social media presence are invisible
5. **Time Sink**: Manual GitHub review takes hours per candidate; founders can't afford this

---

## Market Analysis

### The Hiring Paradox

**For Startups:**

- Early-stage startups lack dedicated HR teams
- Founders' time is extremely valuable (runway is limited)
- Need to hire competent engineers but can't afford extensive vetting processes
- Risk of bad hires is catastrophic at small scale
- Current process: 30-second GitHub glance → "tell me about your project" in interviews (without actually reviewing code)

**For Candidates:**

- Competent developers without large online presence go unnoticed
- AI-assisted development has made it easier to create "pretty" projects with shallow substance
- Hard to differentiate genuine engineering skill from surface-level contributions

### Core Issues with Technical Hiring

1. **Resume Misrepresentation**: Candidates exaggerate skills, list technologies they've barely touched
2. **AI Dependency**: Growing number of developers over-rely on AI (Claude, GitHub Copilot) without understanding fundamentals
3. **Vibe Coding**: Code that looks good superficially but lacks proper error handling, security, scalability
4. **Unknown Talent**: Great engineers working in private repos or without social media presence are invisible
5. **Time Sink**: Manual GitHub review takes hours per candidate; founders can't afford this

---

### Competitive Landscape

| Competitor                                                           | What They Do                       | Limitations                                                                                                     | Our Advantage                                         |
| -------------------------------------------------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **GitHub Native Features**                                           | Contribution graphs, activity feed | - Surface level metrics<br>- Can be gamed with AI commits<br>- No code quality analysis                         | Deep analysis of code architecture, patterns, quality |
| **Coding Assessment Platforms**<br>(HackerRank, Codility, LeetCode)  | Algorithmic problem solving tests  | - Tests algorithms, not real-world engineering<br>- Artificial environment<br>- Doesn't reflect production code | Analyzes actual shipped projects and real-world code  |
| **AI Resume Screeners**<br>(HireVue, Pymetrics)                      | Keyword matching, resume parsing   | - Easily fooled by keyword stuffing<br>- No actual code review<br>- Surface-level analysis                      | Inspects actual code, not just keywords               |
| **Developer Recruiting Platforms**<br>(Hired, TripleByte, Wellfound) | Facilitate interviews, matching    | - Still requires extensive interviewing<br>- No automated technical vetting<br>- Time-intensive                 | Pre-screens technical ability before time investment  |
| **Manual GitHub Review**                                             | Founders/CTOs reviewing code       | - Takes 2+ hours per candidate<br>- Inconsistent criteria<br>- Scalability issues                               | 3-minute automated analysis with consistent metrics   |

### Market Demand Validation

- **Validated with**: Hackathon sponsoring companies (startups and SMBs)
- **Pain Point Confirmed**: Founders are desperate for faster, more reliable technical vetting
- **Willingness to Pay**: Subscription model feasible - saves research time and costly bad hires

---

## Solution Overview

### How Anti-Soy Works

Anti-Soy automatically analyzes GitHub profiles in bulk to assess candidates' genuine engineering ability vs. AI dependency.

**Input:** Batch of GitHub usernames (scan/preload up to 100 profiles)

**Analysis Areas:**

1. **Behavioral Patterns** - How they work over time (refactoring habits, commit patterns, commit quality)
2. **Code Quality** - Architecture decisions, complexity, error handling, scalability
3. **AI Detection** - Identifying AI-generated commits, comments, and code patterns
4. **Security** - API key exposure, security vulnerabilities
5. **Project Authenticity** - Tutorial clones vs original work, real-world problem solving
6. **Engineering Taste** - Dependency choices, naming conventions, documentation, comment quality
7. **Community Engagement** - Open source contributions, PR merge rates
8. **Technological Agility** - Languages and frameworks mastered (>500 LOC projects)

**Output:** Comprehensive ranked dashboard with:

- Ranked list of all candidates by overall score
- Overall skill score (0-100) per candidate
- Category breakdowns (8 dimensions)
- AI dependency percentage
- Security issues flagged
- Strengths and red flags
- Recommended interview questions

### Two-Mode Operation

**Mode 1: Proactive Talent Search**

- Startups search for candidates on GitHub/communities
- Input GitHub username → instant analysis
- Identify promising candidates before outreach

**Mode 2: Application Review (Primary Use Case)**

- Candidate applies with resume + GitHub link
- Upload CSV with GitHub usernames or scan profiles in bulk
- Automated batch analysis runs on up to 100 profiles simultaneously
- HR/founders get instant technical assessment with ranked results
- Review top-ranked candidates first based on comprehensive metrics

### Key Differentiator

Traditional hiring tools analyze resumes or test algorithms. Anti-Soy analyzes **real-world code, behavior patterns, and engineering practices** across multiple dimensions that AI cannot fake.

---

## Discovery vs. Analysis Strategy

### The Real Problem

Startups that already know a GitHub username can manually review profiles. The actual value proposition:

1. **Batch Analysis**: Auto-analyze 100 applications at once
2. **Continuous Monitoring**: Track candidate skill progression over time
3. **Discovery Engine** (future): Find candidates who don't apply directly

### Implementation Priority

**MVP (Current Focus)**: Batch analysis of applications

- Input: List of GitHub usernames from applicants
- Output: Ranked dashboard of all candidates
- Value: Save 2+ hours per candidate review

**Post-MVP**: Discovery mechanisms

- GitHub Search API (find devs by language/location)
- GitHub Trending scraper (identify rising developers)
- Community parsing (HackerNews, Reddit, Dev.to mentions)

---

## Vibe Coder Detection Metrics

### Core Principle

AI can generate clean code, but cannot fake behavioral patterns over time, engineering judgment, security awareness, or deep problem-solving.

### Tier 1: Behavioral & Code Quality (40% weight)

Analyze code structure, architecture, and commit patterns - AI cannot fake sustained engineering discipline or real-world best practices.

| Metric                     | Skilled Developer                                    | Vibe Coder                                     | Detection Method                                          |
| -------------------------- | ---------------------------------------------------- | ---------------------------------------------- | --------------------------------------------------------- |
| **Refactoring Ratio**      | 20-40% of commits revisit existing files             | Most files touched only once                   | Count files with >3 commits vs 1 commit                   |
| **Architecture Decisions** | Clear file organization, test suites, quality README | Flat structure, no tests, minimal docs         | Check for /tests, /docs folders, README length >500 words |
| **Security Awareness**     | No exposed API keys, secure credential management    | Hardcoded secrets, API keys in code            | TruffleHog scan for secrets                               |
| **Error Handling**         | Graceful errors, retry logic, proper logging         | Happy path only, print() debugging             | AST parse for try/catch, logging vs print ratio           |
| **Commit Quality**         | Small, focused commits (<1000 LOC)                   | Massive commits (>10k LOC changed)             | Track commit size distribution                            |
| **Commit Density**         | Consistent, spread over time                         | Clustered in 2-hour AI sprints                 | Analyze timestamp variance                                |
| **Scalability Indicators** | Concurrency patterns, caching, connection pooling    | No performance considerations                  | Grep for async, threading, redis, caching patterns        |
| **Dependency Restraint**   | Minimal, purposeful dependencies                     | 100+ deps for simple app (AI over-engineering) | Count package.json/requirements.txt entries               |
| **Code Comments**          | Strategic comments explaining "why", not "what"      | No comments or AI-generated verbose docstrings | Sample 3 functions, analyze comment patterns              |
| **Stars & Impact**         | Projects with community recognition                  | No engagement or fake stars                    | GitHub star count                                         |

**Why This Matters:** AI can generate clean syntax, but it cannot make architectural decisions, implement proper security, handle edge cases gracefully, or write code that scales. These require experience and judgment.

### Tier 2: AI Detection & Project Authenticity (30% weight)

Detect AI-generated text and identify tutorial clones vs original work.

| Signal                   | Human/Original                                        | AI-Generated/Clone                                                       | Detection                                              |
| ------------------------ | ----------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------ |
| **Commit Messages**      | Casual: "whoops, forgot null case", "fixes issue #42" | Formal: "Implemented null pointer exception handling per best practices" | OpenAI/Claude API analysis for AI probability          |
| **PR Descriptions**      | Context-aware, references specific bugs               | Generic: "Bug fixes and improvements"                                    | Check for issue numbers, specific problem descriptions |
| **Vibe Coding Patterns** | Clean code, proper logging                            | Emojis in code (🚀, ✨), print() instead of logging                      | Regex for emojis, count print vs logging calls         |
| **Tutorial Detection**   | Original projects solving real problems               | Todo app, weather app, blog clone                                        | Compare to list of top 10 common tutorial projects     |
| **Project Authenticity** | Unique features, custom solutions                     | Cookie-cutter template, no customization                                 | OpenAI API: "Does this solve a real-world problem?"    |
| **Company Alignment**    | Tech stack matches company needs                      | Irrelevant technologies                                                  | Optional: Compare project languages to company stack   |
| **Git Message Quality**  | Specific, explains changes                            | One commit with 10k lines changed, no context                            | Analyze commit message length and specificity          |

**Detection Approach:**

- Use OpenAI API (GPT-4o-mini) or Claude API for AI text detection
- Analyze linguistic patterns (formal vs. casual language)
- Check project against common tutorial patterns
- Assess reaCommunity & Technological Agility (30% weight)

Measure open source engagement and breadth of technical skills.

| Metric                        | Good Signal                                       | Poor Signal                                | Detection                                     |
| ----------------------------- | ------------------------------------------------- | ------------------------------------------ | --------------------------------------------- |
| **Open Source Contributions** | Active PRs to external projects, high merge rate  | No external contributions, low merge rate  | GitHub API: count PRs, calculate merge rate   |
| **Community Involvement**     | Part of 5+ GitHub organizations/communities       | Solo projects only                         | Track unique organizations contributed to     |
| **Technological Agility**     | 3+ languages with >500 LOC projects               | Only 1-2 languages                         | Count languages with substantial projects     |
| **Nuanced Languages**         | Rust, Go, Scala, Elixir (advanced)                | Only JavaScript/Python (beginner-friendly) | Bonus points for systems/functional languages |
| **Framework Diversity**       | Multiple frameworks (React, Vue, Django, FastAPI) | Single framework only                      | Track framework variety across repos          |
| **README Documentation**      | >500 words, installation steps, usage examples    | <100 words or missing                      | Word count, sections present                  |

**Why This Matters:** Open source engagement demonstrates collaboration skills and willingness to work on unfamiliar codebases. Technological agility shows adaptability and breadth - skilled engineers learn multiple paradigms, not just what AI prompts suggest
| **Comment Quality** | Strategic depth on complex logic | 0% (none) or 30%+ (excessive) | Comment density, usefulness scoring |
| **Edge Case Handling** | Validates inputs, handles nulls, timezones | Only happy path | Search for validation patterns |

overall_score = (
behavioral_code_quality _ 0.40 +
ai_detection_authenticity _ 0.30 +
community_agility \* 0.30
)

Category Breakdown:

- Behavioral & Code Quality (40%): Refactoring, architecture, security, error handling, commits
- AI Detection & Authenticity (30%): AI text detection, tutorial clones, vibe coding indicators
- Community & Agility (30%): Open source, languages, frameworks, documentation

Interpretation:
80-100: Exceptional (strong engineering fundamentals, diverse skills)
60-79: Skilled (solid ability, minimal red flags)
40-59: Mixed (some concerns, needs deeper vetting)
0-39: High Risk (AI-dependent, poor practices, tutorial clones)

```

**Note:** For technical implementation details including code examples, API integrations, and algorithm
  31-60: Mixed (some AI use, needs vetting)
  61-100: Vibe Coder (high AI dependency, red flag)
```

**Note:** For technical implementation details, see [implementation.md](implementation.md).

---

## Use Cases

### Use Case 1: Proactive Talent Search

**Scenario**: Startup needs a senior backend engineer

**Workflow**:

1. Founder finds candidate on GitHub trending, HackerNews, or community
2. Inputs GitHub username into Anti-Soy
3. Receives analysis in 3 minutes
4. Decides whether to reach out based on scores
5. Uses recommended questions in initial conversation

**Outcome**: Only spend time on high-quality candidates

### Use Case 2: Application Review

**Scenario**: Startup receives 100 applications for frontend role

**Workflow**:

1. Candidate submits resume with GitHub link
2. Anti-Soy automatically analyzes GitHub profile
3. Dashboard ranks all 100 candidates by relevance
4. Founder reviews top 10 in detail
5. Conducts interviews with data-backed questions

**Outcome**: Efficient funnel from 100 → 10 → 3 final candidates

---

## Edge Cases

### Edge Case 1: Private Repository Developers

**Problem**: Great engineers often work in company private repos, no public code

**Solution**:

- OAuth integration: Request access to private repos (with consent)
- Alternative signals:
  - Open source contributions (even if no personal repos)
  - Community engagement (Stack Overflow, GitHub Discussions, forums)
  - Documentation/blog posts demonstrating knowledge
- Partial profile: Flag as "Limited Public Data - Recommend Technical Interview"

### Edge Case 2: Junior Developers

**Problem**: Junior devs may have limited project history

**Solution**:

- Adjust scoring for experience level (inferred from commit history timeline)
- Focus on learning trajectory: Are they improving over time?
- Look for fundamentals: Do small projects demonstrate understanding?
- Potential score: Flag "High Potential - Limited Experience"

### Edge Case 3: AI-Assisted Development (Not AI Dependency)

**Problem**: Distinguishing productive AI use from over-reliance

**Solution**:

- Analyze commit patterns: Do they iterate and refine, or just paste?
- Check for understanding: Do comments/docs show comprehension?
- Look for customization: Is code adapted to specific use case, or generic?
- Nuanced scoring: "AI-Assisted" (good) vs. "AI-Dependent" (red flag)

### Edge Case 4: False Positives - Activity Without Quality

**Problem**: Developer with lots of commits but low-quality code

**Solution**:

- Don't just count commits - analyze commit content
- Measure meaningful contributions (features, bug fixes) vs. noise (typo fixes)
- Code quality metrics catch poor practices even with high activity

---

## Privacy & Ethics

### Data Collection

**What We Collect**:

- Public GitHub data only (unless OAuth consent granted)
- Repository metadata, commit history, code samples
- Public contribution history

**What We Don't Collect**:

- Private repos without explicit consent
- Personal information beyond public GitHub profile
- Data from other platforms without permission

### Legal Compliance

- **GitHub Terms of Service**: Compliant - using public API within rate limits
- **GDPR/Privacy**: Only processing publicly available data
- **Consent**: For private repo access, explicit OAuth flow with clear consent
- **Data Retention**: Analysis results stored for customer, not shared publicly

### Ethical Considerations

**Transparency**:

- Candidates can see what employers see (offer candidate-facing version)
- Clear about what factors influence scoring
- Not a "black box" - explainable AI

**Bias Mitigation**:

- Focus on code quality, not popularity contests
- Don't penalize different coding styles (within reason)
- Avoid proxy discrimination (e.g., GitHub join date as age proxy)

**Limitations Disclosure**:

- Acknowledge: Not a replacement for interviews
- Acknowledge: Limited view if candidate works privately
- Recommend: Use as pre-screening tool, not sole decision factor

---

## Roadmap

### Phase 1: MVP (Current)

- Basic GitHub repo analysis
- Rule-based code quality metrics
- Simple dashboard with scores
- Manual analysis (semi-automated)

### Phase 2: AI Integration

- LLM-powered code review
- AI detection algorithms
- Automated insight generation
- Interview question recommendations

### Phase 3: Scale & Automation

- Batch processing for multiple candidates
- API for ATS integration
- Webhook support (auto-analyze on application submission)
- Enhanced dashboard with comparisons

### Phase 4: Advanced Features

- Private repo OAuth flow
- Custom scoring weights per company
- Team collaboration (share candidate analyses)
- Historical trend tracking (candidate improvement over time)

### Phase 5: Ecosystem Expansion

- GitLab, Bitbucket support
- Stack Overflow integration
- LinkedIn profile analysis (cross-reference)
- Candidate self-assessment tool (freemium lead gen)

---

## Conclusion

Anti-Soy addresses the technical hiring challenge by analyzing real-world GitHub activity to differentiate skilled engineers from AI-dependent developers. The platform saves startups time and money by automating the technical vetting process while providing deeper insights than traditional resume screening.

**For technical implementation details, refer to [implementation.md](implementation.md).**
