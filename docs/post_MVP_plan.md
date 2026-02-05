possible things to work on

- frontend styling
- we can keep db the way it is as opening up to only a few users.
- add features
  1. Resume Parser: to parse github link from resume, and traverse there
  2. Github Scraper: to scrape github with criteria set up per company, providing potential talents without any
     talent user base to start with
  3. Company sign up page: Allow for basic company information, and then description
     - additional question on what they value most, and can adjust internal algorithm to match it

## V2 Post-MVP Enhancements

### LLM-Powered Checks (Deferred from MVP)

- **Print/Logging Quality Evidence**: Use LLM to analyze print statements for patterns like:
  - Emoji-heavy debug prints (🔥, 💀, etc.) - strong AI/junior signal
  - Actual error messages vs "it broke lol"
  - Structured logging vs scattered prints
- **Comment Quality Analysis**: LLM to detect:
  - Comments that just repeat the code
  - Sarcastic/unprofessional comments
  - Overly verbose AI-style explanations

---

- add improvements/fixes. most important question: after we get teh metric, how do we present it in an insightful way? How do we present them together as bundled insights that can power a decision instead of individual metrics?
  1. For each metrics, needs improvement on how each is anlayzed
  2. More robust AI detection
  - Add another metric to count the number of md files, and put their names into a list. AI coding agent summaries are obvious and their contents are obvious. We can also see if the user employs good AI coding agent using guidelines in their mds, like instructions for checks on security and privacy. This can be interplayed with the security section.
  3. Equations/formulas to join relevant and even seemingly non-relevant metrics together

before demoing to customers (which is in 2 weeks)

priority:

- give meaning to metrics
- more robust AI detection
- labeling of most recent repo to least (if unordered, emplolyers can not tell difference between toy projects and actual projects)
