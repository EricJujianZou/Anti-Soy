# Anti-Soy: Hackathon Duo Scan — Technical PRD

**Branch:** `hackathon-main-flow`
**Stage:** 1 MVP (Stage 2 items explicitly excluded)
**Feature freeze:** Friday March 7, 6 PM

---

## 1. Overview

This PRD covers the implementation of the Hackathon Duo Scan feature:

- **2.2 Duo Scan** — analyze two GitHub repos side-by-side, show profile cards + compatibility block
- **2.3 Ranking System** — 5-tier rank system with deterministic rule-based assignment + LLM contextual blurb
- **2.4 Landing Page Updates** — update `/hacker` page to support dual input mode, redesigned result screen

---

## 2. Design Reference

Design files are in `client/design/`. They are WIP — use them as directional, not pixel-perfect specs.

| File | Description |
|---|---|
| `rank card.png` | Individual rank card layout ("pokemon card" style) |
| `stitch 1 summary.png` | Summary view of a scan |
| `stitch 2 sample matchmake.png` | Duo matchmaking sample layout |
| `stitch 3 comaptibility matchmake.png` | Compatibility block layout |

When design is unclear or missing, implement with best judgment aligned to the existing hacker theme (`hsl(var(--hacker))` for cyan accent, dark grid background).

---

## 3. Parallel Workstream Structure

The following three branches have **zero cross-dependencies** and must be built in parallel.
The final Integration Phase is sequential and must be done **after all three branches are complete**.

```
Branch A: Backend /compatibility endpoint    ─┐
Branch B: Frontend RankCard component        ─┼─→ Integration Phase (sequential)
Branch C: Frontend HackerPage layout shell   ─┘
```

---

## 4. Branch A — Backend: `/compatibility` Endpoint

**Agent memory scope:** `server/` only
**No frontend deps. No coupling to Branches B or C.**

### 4.1 What to Build

A new POST endpoint at `/compatibility` that accepts two complete scan result payloads and returns:
1. A rule-based numerical compatibility score
2. A short LLM-generated compatibility narrative
3. Structured complementary strength callouts
4. Structured conflict/gap flags

### 4.2 Request Schema

Add to `server/v2/schemas.py`:

```python
class ScanResultInput(BaseModel):
    """Mirrors client-side AnalysisResponse + EvaluationEvent"""
    repo_url: str
    verdict: dict  # { type: str, confidence: float }
    ai_slop: dict  # AISlop schema
    bad_practices: dict  # BadPractices schema
    code_quality: dict  # CodeQuality schema
    languages: dict[str, int]  # from repo.languages
    standout_features: list[str]
    business_value: dict | None  # BusinessValue schema, nullable if eval failed
    hackathon_context: str | None = None  # optional, free text

class CompatibilityRequest(BaseModel):
    person_a: ScanResultInput
    person_b: ScanResultInput
    hackathon_context: str | None = None
```

### 4.3 Response Schema

Add to `server/v2/schemas.py`:

```python
class CompatibilityCallout(BaseModel):
    type: Literal["strength", "flag"]
    message: str  # e.g. "Person A does React, Person B does C++ — strong frontend/backend split"

class CompatibilityResponse(BaseModel):
    score: int  # 0–100
    score_label: str  # e.g. "Strong Pair", "Risky Pair", "Redundant Skills"
    narrative: str  # 2-3 sentence LLM-generated blurb
    callouts: list[CompatibilityCallout]  # mix of strengths + flags
```

### 4.4 Rule-Based Compatibility Score Algorithm

Implement in a new file `server/v2/compatibility_scorer.py`.

**Inputs used:** languages dict, verdict type, ai_slop score, code_quality score, bad_practices score, standout_features.

**Scoring components (total = 100 points):**

| Component | Points | Logic |
|---|---|---|
| Role coverage | 0–40 | Measures how complementary language stacks are. High if one is frontend-dominant (JS/TS) and other is backend/systems (Python, Go, Rust, C++). Low if both identical stacks. |
| Skill diversity bonus | 0–20 | Count unique top languages across both. >4 unique languages = full 20. <2 unique = 0. |
| Vibe coder penalty | −20 per person | If `verdict.type == "vibe_coder"`, deduct 20. Max deduction −40. |
| Code quality floor | 0–20 | Average of both `code_quality.score`. Scaled: 80+ = 20pts, 50–79 = 10pts, <50 = 0pts. |
| Completeness bonus | 0–20 | Both have non-empty standout_features and business_value = full bonus. |

**Score label mapping:**
- 80–100: `"Strong Pair"`
- 60–79: `"Good Match"`
- 40–59: `"Workable"`
- 20–39: `"Risky Pair"`
- 0–19: `"Avoid"`

**Callouts generation (deterministic, no LLM):**

Generate callouts by:
1. Language overlap: if dominant language matches between both → flag "Both are [lang]-heavy, no coverage differentiation"
2. Role split: if frontend vs backend clearly split → strength "Person A brings [stack], Person B brings [stack] — strong coverage split"
3. Vibe coder: if either has `verdict.type == "vibe_coder"` → flag "Person [A/B] flagged as vibe coder — probe their understanding"
4. Both rejected: if both `is_rejected` → flag "Neither project shows meaningful technical depth"
5. Hackathon context: if `hackathon_context` is provided and contains a keyword (e.g. "hardware", "health"), append to LLM prompt for contextual weighting (do not change rule-based score)

### 4.5 LLM Compatibility Narrative

Add a new prompt function in `server/prompt_modules.py`:

```python
def build_compatibility_prompt(
    person_a: dict,
    person_b: dict,
    rule_score: int,
    callouts: list[dict],
    hackathon_context: str | None
) -> str:
    ...
```

**Prompt guidelines:**
- Pass both summaries (verdict, languages, standout features) as delimited blocks — never interpolate raw repo content into system prompt
- Ask the LLM to write 2–3 sentences describing how well this pair would collaborate at a hackathon
- If `hackathon_context` is provided, ask it to factor that into the narrative
- Temperature: `0.3` (consistency > creativity)
- Target output: 2–3 sentences, no lists, no markdown headers in the output
- System prompt must instruct the LLM: "You are evaluating hackathon team compatibility. Be direct and actionable. Do not roast. Do not be vague."

### 4.6 Endpoint in `server/main.py`

```python
@app.post("/compatibility", response_model=CompatibilityResponse)
async def check_compatibility(request: CompatibilityRequest):
    ...
```

**Rate limit:** apply same rate limiter as `/analyze` (10 req/IP/hour).
**Error handling:** If LLM call fails, return response with `narrative = ""` and `score` + `callouts` still populated from rule-based logic — never fail the full request because of an LLM timeout.

### 4.7 Tests

Create `server/tests/test_compatibility.py`:
- Unit test `compatibility_scorer.py` with at least 4 fixture pairs:
  1. Clean frontend dev + clean backend dev → high score
  2. Two identical JS-only vibe coders → low score
  3. One vibe coder + one cracked dev → medium score with vibe coder flag
  4. Both rejected repos → low score with depth flag
- Integration test `/compatibility` endpoint with mocked LLM call

---

## 5. Branch B — Frontend: `RankCard` Component + Tier Mapping + Export

**Agent memory scope:** `client/src/` only
**No backend deps. Use mock `AnalysisResponse` + `EvaluationEvent` data during development.**
**No coupling to Branches A or C.**

### 5.1 What to Build

A new `RankCard` component that displays a single scan result in a "pokemon card"-style shareable format. This will be used in both the single scan result view and the duo scan split-screen.

### 5.2 Tier Mapping Logic

Create `client/src/utils/rankTier.ts`.

**5 tiers (deterministic, no LLM):**

| Tier Label | Condition |
|---|---|
| `"Vibe Coder"` | `verdict.type === "vibe_coder"` |
| `"I did a tutorial"` | `verdict.type === "junior"` AND `ai_slop.score < 0.5` |
| `"Enthusiast"` | `evaluation.standout_features.length > 0` AND verdict is not vibe_coder AND verdict is not senior |
| `"CRACKED"` | `evaluation.standout_features.length > 0` AND `evaluation.business_value.solves_real_problem === true` AND `verdict.type === "senior"` |
| `"Virgin"` | `"CRACKED"` conditions met AND `code_quality.score >= 80` AND `bad_practices.score <= 20` |

Priority order (evaluate top to bottom, first match wins):
1. Virgin
2. CRACKED
3. Vibe Coder
4. Enthusiast
5. I did a tutorial (fallback)

Export from `rankTier.ts`:
```typescript
export type Tier = "Virgin" | "CRACKED" | "Enthusiast" | "I did a tutorial" | "Vibe Coder";

export interface TierResult {
  tier: Tier;
  color: string;     // CSS color string for the tier badge
  description: string; // short static description, e.g. "Writes real code, ships real things"
}

export function getTier(
  analysis: AnalysisResponse,
  evaluation: EvaluationEvent | null
): TierResult
```

**Tier colors (match hacker theme palette, dark background friendly):**
- Virgin: `#a855f7` (purple)
- CRACKED: `#22c55e` (green)
- Enthusiast: `#3b82f6` (blue)
- I did a tutorial: `#f59e0b` (amber)
- Vibe Coder: `#ef4444` (red)

### 5.3 `RankCard` Component

Create `client/src/components/RankCard.tsx`.

**Props:**
```typescript
interface RankCardProps {
  analysis: AnalysisResponse;
  evaluation: EvaluationEvent | null;
  label?: "Person A" | "Person B" | undefined; // shown in duo mode only
  hackerContext?: string | null;
}
```

**Card sections (top to bottom):**

1. **Header bar** — repo name, owner avatar (from GitHub URL), tier badge with tier color
2. **Tier display** — large tier label (e.g. "CRACKED"), tier description line below
3. **Language bar** — mini horizontal bar chart of top 3 languages by byte count (from `analysis.repo.languages`)
4. **Vibe coder flag** — if tier is "Vibe Coder", show a prominent red banner: `"AI Slop Detected — [confidence level]"`
5. **Top strength** — first item from `evaluation.standout_features` (or `—` if none). Label: "Top Signal"
6. **Key flags** — up to 2 items from `analysis.bad_practices.findings` with highest severity. Label: "Flags"
7. **Score row** — three mini score chips: AI Slop `[score]%` | Code Quality `[score]%` | Bad Practices `[score]%`
8. **Export buttons row** — `[ Save as Image ]` and `[ Copy Image ]` buttons (see 5.4)

**Visual style:**
- Dark card with border in tier color
- Monospace font for scores (matches existing `font-mono` convention)
- Fixed width: `380px` — important for html2canvas capture
- Fixed minimum height — card must not reflow based on content length (use truncation/ellipsis for long text)
- Card must be fully self-contained visually — do not rely on page background for readability

### 5.4 Image Export (html2canvas)

Install dependency: `html2canvas` (npm package).

Add to `RankCard.tsx`:

```typescript
import html2canvas from "html2canvas";
```

**Save as Image:**
- Capture the card's container `div` ref using `html2canvas(ref.current, { useCORS: true, scale: 2 })`
- Trigger browser download as `.png` filename: `antisoy-[reponame]-[tier].png`

**Copy Image:**
- Render to canvas via html2canvas
- Call `canvas.toBlob()` then `navigator.clipboard.write([new ClipboardItem({ "image/png": blob })])`
- Show inline feedback: button text changes to `"Copied!"` for 2 seconds

**Error handling:** If clipboard API is unavailable (non-HTTPS or unsupported browser), fall back to showing the image in a modal with a "Right-click to save" instruction.

### 5.5 Tests

Create `client/src/test/rankTier.test.ts`:
- Unit test all 5 tier conditions with fixture data covering every branch
- Test priority order (e.g., a Virgin-eligible profile should NOT return CRACKED)

---

## 6. Branch C — Frontend: HackerPage Layout Shell

**Agent memory scope:** `client/src/pages/HackerPage.tsx` and closely related components only
**No backend deps. No RankCard deps — use placeholder `<div>` where cards will go.**
**No coupling to Branches A or B.**

### 6.1 What to Build

Update `HackerPage.tsx` to support a **mode toggle** between Solo scan and Duo scan, and build the structural layout shell for Duo mode. No analysis logic — just the UI layout and navigation.

### 6.2 Mode Toggle

Add a toggle above the input area:

```
[ Solo Scan ]  [ Duo Scan ]
```

- Default: Solo Scan (existing behavior, no change to existing flow)
- Duo Scan: replaces single TerminalInput with side-by-side dual input (see 6.3)
- Use local `useState<"solo" | "duo">` — no URL params needed for the toggle state itself

Style: match the existing cyan hacker theme. Use the same `--hacker` CSS variable for the active tab underline/border.

### 6.3 Duo Scan Input Layout

When mode is `"duo"`:

Replace the single `<TerminalInput>` with:
- Two `<TerminalInput>` components side by side (grid, `grid-cols-2`, gap-6)
- Label above each: `"Person A"` and `"Person B"` in muted text
- Below both inputs: a single `[ Analyze Both ]` submit button (full width, hacker-themed)
- Validation: both URLs must be present and contain `github.com` before submit is enabled
- On mobile (`sm` breakpoint): stack vertically instead of side-by-side

**Props to pass each TerminalInput:**
- `hidePriorities={true}`
- `placeholder` appropriate to each position (e.g. `"https://github.com/teammate-a/repo"`)
- `examples` — update examples for duo mode (see 6.4)

### 6.4 Updated Example Buttons

For duo mode, examples should be **paired** — clicking one example loads into both inputs:

```typescript
const DUO_EXAMPLES = [
  {
    label: "Frontend + Backend",
    urlA: "https://github.com/EricJujianZou/PromptAssist",
    urlB: "https://github.com/Skullheadx/The-Traveling-Salesman-Problem",
  },
  {
    label: "Two Vibe Coders",
    urlA: "https://github.com/chaosium43/METROHACKS22",
    urlB: "https://github.com/EricJujianZou/PromptAssist",
  },
];
```

Replace the existing single-URL example buttons with paired buttons that fill both inputs atomically.

### 6.5 Hackathon Context Input

Below the two URL inputs (duo mode only), add:

```
[ Optional: What's the hackathon focus? e.g. "healthtech", "hardware" ]
```

- Plain `<input type="text">` styled to match the hacker theme (monospace, dark, thin border)
- Max length: 100 characters
- Store in local state: `const [hackerContext, setHackerContext] = useState("")`
- Pass to navigation params when submitting duo scan

### 6.6 Duo Scan Submit Navigation

On `[ Analyze Both ]` click:

```typescript
const params = new URLSearchParams({
  linkA: urlA,
  linkB: urlB,
  mode: "duo",
  ...(hackerContext ? { context: hackerContext } : {}),
});
navigate(`/duo?${params.toString()}`);
```

This routes to a new `/duo` route (created in Integration Phase). Branch C only builds the navigation — it does NOT build the destination page.

### 6.7 Copy Changes to `main.tsx` / Router

Add the `/duo` route to `App.tsx` as a placeholder:

```tsx
<Route path="/duo" element={<div>Duo scan coming soon</div>} />
```

This allows Branch C to be testable in isolation without the Integration Phase being done.

---

## 7. Integration Phase (Sequential — After All Branches)

**Must be done AFTER Branches A, B, and C are all complete.**
**Same agent, same memory, sequential phases.**

### Phase 1 — Wire Single Scan to RankCard

**Goal:** Replace the existing `RepoAnalysis.tsx` hacker-mode result display with the new `RankCard`.

- In `RepoAnalysis.tsx`, check `searchParams.get("mode") === "hacker"`
- If hacker mode: render `<RankCard analysis={analysis} evaluation={evaluation} />` instead of (or below) the existing detailed breakdown
- The existing detailed recruiter layout should remain unchanged for non-hacker mode

### Phase 2 — Build `DuoScanPage.tsx`

Create `client/src/pages/DuoScanPage.tsx`.

**Route:** `/duo` (already registered as placeholder in Branch C)

**Behavior:**

1. Read `linkA`, `linkB`, `mode`, `context` from URL search params
2. Fire two parallel `useAnalyzeStream` calls simultaneously — one for each URL
   - Use two separate hook instances: `const streamA = useAnalyzeStream()` and `const streamB = useAnalyzeStream()`
   - Start both in the same `useEffect` on mount
3. Show loading state: two side-by-side `ProgressTracker` components while analyzing
4. When both streams complete (`streamA.isDone && streamB.isDone`):
   - Render two `<RankCard>` components side-by-side (`grid-cols-2`)
   - Below the cards, show the compatibility block (Phase 3)
   - On mobile: stack vertically

**Error handling:** If one stream fails, show that card's error state while still attempting the other. Do not block the compatibility call if one fails — pass null for the failed result.

### Phase 3 — Compatibility Block

After both streams complete, call `POST /compatibility`:

```typescript
const compatResult = await api.checkCompatibility({
  person_a: buildScanInput(streamA.analysis, streamA.evaluation, linkA),
  person_b: buildScanInput(streamB.analysis, streamB.evaluation, linkB),
  hackathon_context: context || null,
});
```

Add `checkCompatibility` to `client/src/services/api.ts`:
```typescript
export interface CompatibilityCallout {
  type: "strength" | "flag";
  message: string;
}

export interface CompatibilityResponse {
  score: number;
  score_label: string;
  narrative: string;
  callouts: CompatibilityCallout[];
}

checkCompatibility: async (request: CompatibilityRequest): Promise<CompatibilityResponse> => {
  const res = await fetch(`${API_BASE_URL}/compatibility`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  ...
}
```

**Compatibility Block UI:**

Render between/below the two RankCards:

```
┌─────────────────────────────────────────┐
│  Compatibility Score: 74/100 — Good Match│
│  [narrative text here]                  │
│                                         │
│  ✓ Strong frontend/backend split        │
│  ✓ Both have novel project ideas        │
│  ⚠ Person B flagged as vibe coder       │
└─────────────────────────────────────────┘
```

- Score bar: animated fill bar (0–100) in the appropriate tier color
- Callout icons: `✓` green for strengths, `⚠` amber for flags
- LLM narrative in muted italic text

### Phase 4 — Mobile + Polish

- Test full duo scan flow at `375px` viewport width
- Cards stacked vertically on mobile; compatibility block full width below both
- Verify html2canvas export works on both cards independently
- Touch-test `[ Copy Image ]` button behavior (clipboard API may be unavailable on some mobile browsers — ensure fallback renders)

---

## 8. Data Flow Summary

```
User pastes two GitHub URLs + optional hackathon context
  │
  ▼
/duo?linkA=...&linkB=...&mode=duo&context=...
  │
  ├─→ useAnalyzeStream(linkA) ─→ SSE stream to existing /analyze/stream
  │     returns: AnalysisResponse + EvaluationEvent
  │
  ├─→ useAnalyzeStream(linkB) ─→ SSE stream to existing /analyze/stream
  │     returns: AnalysisResponse + EvaluationEvent
  │
  └─→ POST /compatibility (after both complete)
        accepts: { person_a, person_b, hackathon_context }
        returns: CompatibilityResponse
          │
          ├─ rule-based score (no LLM)
          ├─ LLM narrative (~200ms extra latency)
          └─ callouts (deterministic)
```

---

## 9. File Map

| File | Branch | Action |
|---|---|---|
| `server/v2/schemas.py` | A | Add `ScanResultInput`, `CompatibilityRequest`, `CompatibilityResponse`, `CompatibilityCallout` |
| `server/v2/compatibility_scorer.py` | A | New file — rule-based scoring + callout generation |
| `server/prompt_modules.py` | A | Add `build_compatibility_prompt()` |
| `server/main.py` | A | Add `POST /compatibility` endpoint |
| `server/tests/test_compatibility.py` | A | New test file |
| `client/src/utils/rankTier.ts` | B | New file — tier mapping logic |
| `client/src/components/RankCard.tsx` | B | New component — rank card + export |
| `client/src/test/rankTier.test.ts` | B | New test file |
| `client/src/pages/HackerPage.tsx` | C | Mode toggle + duo input layout + navigation |
| `client/src/App.tsx` | C | Add `/duo` placeholder route |
| `client/src/pages/DuoScanPage.tsx` | Integration | New page — duo scan orchestration |
| `client/src/services/api.ts` | Integration | Add `CompatibilityRequest`, `CompatibilityResponse` types + `checkCompatibility` function |
| `client/src/pages/RepoAnalysis.tsx` | Integration | Hacker mode → render RankCard |

---

## 10. Guardrails (Non-Negotiable)

- No API keys or tokens in client code. `/compatibility` calls LLM server-side only.
- Validate GitHub URLs server-side before processing in `/compatibility` (regex check).
- GitHub README/repo content passed to LLM must be wrapped in delimiters (existing pattern in `prompt_modules.py` — follow it).
- Never execute code from analyzed repos.
- LLM model version pinned (same model as existing LLM calls — do NOT auto-select or upgrade).
- Temperature `0.3` for the compatibility narrative call.
- If the repo scan result contains `is_rejected: true`, still compute compatibility score but note it in callouts.
- html2canvas: capture only the card element, not the full page.

---

## 11. Out of Scope (Do Not Build)

Per spec section 2.5 — these are Stage 2 and must NOT be built:

- User auth or GitHub OAuth
- Database storage of scan results
- URL-based shareable links (instead: image export only)
- Active matchmaking algorithm
- LinkedIn scanning
- Analytics overhaul
- Soft skills detection
- Batch scanning for hacker side
