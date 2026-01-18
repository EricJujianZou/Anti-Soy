# Anti-Soy

Startups are struggling to find good candidates and good candidates don't hear about startups.

# The problem

It is very difficult for companies to find **competent** technical people who know their stuff.

- many people overly misrepresent their skills on their resume
- too reliant on AI and will only every be as smart as Claude
- dont have a large online presence / are unknown

# Traditional solutions

- Extensive interviewing and research by HR/senior devs
- Headhunting on social media
- Interviewing

# Our Solution

- look on candidate github
  - scan the repos
    - look for architecture decisions, why did you pick this level of abstraction for your api/app?
      - files organized, test suites, readme good documentation
    - security
      - API keys (truffle hog)
    - error handling (do you only handle the happy path? what about edge cases)
      - error handling present at all. graceful error handling (retry, logging)
    - vibe coded?
      - ai comments emojis in logging.
      - print statements instead of logging
    - how many dependencies do you have?
    - git messages and prs.
      - one commit with 10k lines changed
      - commit density
    - Scalable?
      - concurrency
      - caching
    - stars
    - comments in code?
      - do they explain the function. just choose 3 funcs to evaluate
    - does your project actually do something?
      - check top 10 projects to make and see if this project is one of them.
      - use llm to see if project aligns with company
      - use llm to see if project solves a real world problem
  - look for open source contributions (gh api call)
    - part of which online communities?
    - how many prs get merged
  - technological agility
    - how many languages / frameworks are you competant in (projects >500 lines of code)
      - look at nuanced languages

Provide a dashboard to analyze candidates. Give interviewers hints as to what to ask about to know candidate deeper.

## Input

github username

## Output

- ability to ship real features.
- production ready software engineer
- good practices
- have community recognition
- ability to adapt to the company's stack
