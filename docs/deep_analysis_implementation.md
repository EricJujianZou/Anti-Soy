# Deep Analysis Implementation (Post-MVP)

Features that require LLM inference. Implement after basic feature extraction + ML classifier is working.

---

## 1. Comment Verification (LLM)

**Current MVP approach:** Pattern-match to detect "obvious" comments (e.g., `# increment i`, `// loop through array`).

**Deep analysis enhancement:**

- Extract `(comment, following_code)` pairs
- Send to LLM: "Does this comment add value, or does it just restate the code?"
- LLM can catch subtle cases pattern matching misses

**Implementation:**

```python
# MVP: Pattern match for obvious patterns
REDUNDANT_PATTERNS = [
    r"#\s*(increment|decrement|add|subtract)\s+\w+",
    r"#\s*(loop|iterate)\s+(through|over)",
    r"#\s*(set|assign)\s+\w+\s+to",
    r"#\s*(return|returns)\s+(the\s+)?\w+",
]

# Deep analysis: LLM verification
def verify_comment_quality(comment: str, code: str) -> bool:
    prompt = f"Comment: {comment}\nCode: {code}\nDoes this comment add value beyond restating the code? yes/no"
    return llm.call(prompt) == "yes"
```

---

## 2. Whitespace Naturalness Score (DetectCodeGPT)

**Research finding:** Machine code has MORE regularized whitespace; human code has "random" whitespace patterns. Whitespace tokens showed the **highest deviation** in naturalness between human/machine code.

**Deep analysis approach (from paper):**

1. Perturb code by inserting random spaces/newlines
2. Compute log-rank score change using an LLM
3. Sharp drop = machine-generated; small change = human

**Why skip for MVP:** Requires LLM inference per file, expensive and slow.

**MVP approximation:** Simple heuristics without LLM:

- `whitespace_consistency`: Measure variance in indentation patterns
- `newline_clustering`: Are blank lines evenly distributed or clustered?

---

## 3. Token Naturalness / Perplexity

**Research finding:** Machine code has higher "naturalness" (lower perplexity) because LLMs generate predictable token sequences.

**Deep analysis approach:**

- Run code through CodeLlama/similar
- Compute average log-likelihood per token
- Higher likelihood = more likely machine-generated

**Why skip for MVP:** Requires model inference.

---

## 4. Lexical Diversity (Zipf/Heaps Laws)

**Research finding:**

- Machine code has shallower Heaps' Law slope (slower vocabulary growth)
- Machine prefers tokens ranked 10-100 (common but not universal)

**MVP approach:** We already capture this via:

- `unique_word_ratio` (lexical diversity)
- `naming_consistency` (limited vocabulary = high consistency)

**Deep analysis enhancement:**

- Fit Heaps' Law curve, compare slope to human baseline
- Analyze token rank distribution

---

## 5. Cross-File Semantic Consistency

**Question to answer:** "Does the code across files show coherent understanding, or isolated snippets?"

**Deep analysis approach:**

- Extract function signatures across files
- LLM: "Do these functions form a coherent API? Are naming conventions consistent with apparent intent?"

**Why skip for MVP:** Requires understanding semantics, not just syntax.

---

## 6. Commit Message Analysis

**Signal:** AI-generated commit messages are often generic ("Update file", "Fix bug", "Add feature").

**Deep analysis approach:**

- Extract commit messages from git history
- LLM: "Rate specificity and technical accuracy of these commit messages"

**MVP approach:** Pattern-match for generic messages, count ratio.

---

## Key Findings from DetectCodeGPT Paper

| Signal            | Human Code                       | Machine Code                   |
| ----------------- | -------------------------------- | ------------------------------ |
| Whitespace        | Random, personal style           | Regularized, predictable       |
| Lexical diversity | Rich, varied tokens              | Narrow spectrum (ranks 10-100) |
| Code length       | Longer (extensibility, comments) | More concise                   |
| Comments          | Context-aware                    | More frequent at high temp     |
| Error handling    | Variable                         | Heavy use of raise/TypeError   |
| OOP boilerplate   | Moderate                         | Heavy (**class**, **name**)    |

---

## Implementation Priority

After MVP classifier is trained:

1. **Comment verification** - High value, moderate cost
2. **Whitespace naturalness** - High value, high cost
3. **Commit message analysis** - Medium value, low cost
4. **Cross-file consistency** - Medium value, high cost
5. **Token perplexity** - Research interest, high cost
