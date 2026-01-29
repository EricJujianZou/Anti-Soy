# Anti-Soy V2: Product Vision

> **Pivot Summary:** From "generic code quality scores" to "interview weapons — specific evidence + pointed follow-up questions."

---

## Table of Contents

1. [Problem Space](#problem-space)
2. [Why V1 Wasn't Enough](#why-v1-wasnt-enough)
3. [The V2 Solution](#the-v2-solution)
4. [Competitive Differentiation](#competitive-differentiation)
5. [Target Users](#target-users)
6. [Privacy & Ethics](#privacy--ethics)

---

## Problem Space

### The Hiring Paradox

**For Startups:**

- No dedicated HR teams; founders' time is extremely valuable
- Risk of bad hires is catastrophic at small scale
- Current process: 30-second GitHub glance → generic "tell me about your project" in interviews

**For Candidates:**

- AI-assisted development has made it easy to create "pretty" projects with shallow substance
- Hard to differentiate genuine engineering skill from surface-level contributions

### Core Issues

1. **Vibe Coding:** Code that looks good superficially but lacks proper error handling, security, scalability
2. **AI Dependency:** Developers over-rely on AI without understanding fundamentals
3. **Resume Misrepresentation:** Candidates list technologies they've barely touched
4. **Time Sink:** Manual GitHub review takes hours per candidate

---

## Why V1 Wasn't Enough

V1 delivered **14 individual metrics** (test coverage, error handling, commit density, etc.) with scores 0-100.

**Problems we discovered:**

| Issue                      | Impact                                                                                 |
| -------------------------- | -------------------------------------------------------------------------------------- |
| Metrics were shallow       | Single-signal detection (e.g., "has try/catch" = good error handling) is easily fooled |
| Scores were meaningless    | "Error Handling: 72" — what does a recruiter do with this?                             |
| No differentiation         | Candidates clustered around 50-70 range; couldn't distinguish clearly                  |
| AI can fake best practices | A vibe coder using AI can still produce code with try/catch blocks                     |
| Output wasn't actionable   | Interviewers got numbers, not ammunition                                               |

**The core insight:** A weighted average of shallow metrics produces a confident-sounding bullshit detector that is itself bullshit.

---

## The V2 Solution

### Core Principle

**We don't just give scores. We arm interviewers with specific evidence and pointed questions to probe candidate understanding.**

### What We Deliver

**For each candidate, Anti-Soy provides:**

1. **Specific Evidence** — Actual code snippets from their repo with file:line references
2. **Plain-English Explanations** — Why this is a red flag or strength
3. **Interview Questions** — Pointed follow-up questions based on their actual code

### Example Output

> **🚨 Flag: No input validation on user endpoint**
>
> ```python
> # From: api/users.py:47
> def update_user(user_id, data):
>     db.users.update(user_id, data)  # No validation
> ```
>
> **Ask them:** "What happens if someone passes `{"role": "admin"}` in this data payload? How would you prevent privilege escalation?"

This is gold for interviewers. They don't need to understand code — they read the question and watch the candidate confidently explain or struggle.

### The Key Insight

**AI is reactive, not proactive.** It does what you tell it. A competent dev knows what to tell it. A vibe coder doesn't know what they don't know.

We detect **absences of defensive thinking** — things that require knowing to ask:

- Input validation
- Rate limiting
- Auth checks
- Error handling beyond happy path
- Security considerations

AI doesn't add these unless explicitly prompted. A vibe coder doesn't know to prompt for them.

---

## Competitive Differentiation

| Competitor                                  | What They Do                   | Their Output          | Our Output                                                                |
| ------------------------------------------- | ------------------------------ | --------------------- | ------------------------------------------------------------------------- |
| Code quality tools (SonarQube, CodeClimate) | Static analysis                | "Code smell detected" | "Here's the code, here's why it's bad, ask them this question"            |
| AI code detectors                           | Binary AI/human classification | "78% AI-generated"    | "This comment pattern suggests AI, ask them to explain the algorithm"     |
| Coding assessments (HackerRank)             | Algorithmic tests              | "Passed 8/10 tests"   | "In their actual shipped code, they missed X — probe their understanding" |
| Manual GitHub review                        | Founders skim repos            | Gut feeling           | Systematic evidence with traceable findings                               |

**Our moat:** Everyone else gives a score. We give an interview weapon.

---

## Target Users

### Primary: Hiring Managers at Startups

- Not deeply technical themselves, but work with technical teams
- Need to filter 100 applicants down to 10 interviews
- Want confidence that they're not wasting time on vibe coders
- Value: Specific questions to ask, not just scores to interpret

### Secondary: Technical Recruiters

- Screen candidates before passing to engineering
- Need quick signal on "is this worth engineering's time?"
- Value: Evidence to include in candidate summary

---

## Privacy & Ethics

**Unchanged from V1:**

- **Data:** Public GitHub data only (unless OAuth consent granted)
- **Compliance:** GitHub ToS compliant, GDPR compliant (public data)
- **Transparency:** Explainable findings — we show our work
- **Limitations:** Not a replacement for interviews; a tool to make interviews better

**V2 Addition:**

- **Evidence-based:** Every finding is traceable to specific code
- **No black boxes:** Interviewers can verify any claim we make
- **Candidate fairness:** Findings are based on what's in their code, not proxies like GitHub stars or activity graphs

---

## Success Metrics

| Metric                 | Target                                                     |
| ---------------------- | ---------------------------------------------------------- |
| Interviewer confidence | "I knew exactly what to ask" feedback                      |
| Time saved             | <5 min to understand candidate vs 2+ hours manual review   |
| Differentiation        | Clear separation between candidates (not clustered scores) |
| Question usage         | Interviewers actually use our generated questions          |

---

## What's Next

For technical implementation details, architecture decisions, and engineering specifications, see [implementationV2.md](implementationV2.md).
