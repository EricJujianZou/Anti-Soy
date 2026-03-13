# Landing Page Resume Button Refactor — Tech Spec

## Problem Statement

On the landing page (`Index.tsx`), the "UPLOAD CANDIDATE RESUMES" CTA is rendered as a large, full-width bordered rectangle that visually suggests a drag-and-drop zone. This confuses users — they expect to drop files on it, but it is actually a navigation button to the `/upload` page. It needs to look clearly like a clickable button, not a drop target.

**IMPORTANT:** This spec concerns ONLY the landing page (`Index.tsx` and the secondary-action rendering inside `TerminalInput.tsx`). Do NOT modify the actual drag-and-drop component on the `/upload` page (`UploadPage.tsx`).

## User Story

> "As a recruiter visiting the landing page, I want the resume upload option to be obviously a clickable button so I know to click it to go to the upload page, rather than trying to drag files onto it."

## Current Implementation (What Exists Today)

### File: `client/src/components/TerminalInput.tsx`, lines 72-108

The `TerminalInput` component accepts an `onSecondaryAction` prop. When provided, it renders a full-width button block **above** the GitHub URL input, followed by an "or paste a github url" divider.

The current button markup (lines 76-98):

```tsx
<button
  type="button"
  onClick={() => onSecondaryAction(prioritiesArray())}
  className={cn(
    "w-full border-2 border-primary/70 bg-primary/5 backdrop-blur-sm",
    "py-5 px-6 text-center",
    "uppercase tracking-widest text-sm font-bold text-primary",
    "transition-all duration-300",
    "hover:bg-primary/15 hover:border-primary hover:glow-amber",
    "relative group"
  )}
>
  {/* Four corner bracket decorations */}
  <span className="absolute -top-px -left-px text-primary text-sm">&#9484;</span>
  <span className="absolute -top-px -right-px text-primary text-sm">&#9488;</span>
  <span className="absolute -bottom-px -left-px text-primary text-sm">&#9492;</span>
  <span className="absolute -bottom-px -right-px text-primary text-sm">&#9496;</span>
  <span className="flex items-center justify-center gap-2">
    Upload Candidate Resumes
  </span>
  <span className="block text-[10px] text-muted-foreground font-normal mt-1 tracking-wider normal-case">
    Batch analyze up to 10 resumes at once
  </span>
</button>
```

**Why it looks like a drop zone:**
- `w-full` makes it span the entire form width (~672px on desktop via `max-w-2xl`)
- `border-2` gives it a thick border (thicker than other elements)
- `py-5 px-6` gives it generous internal padding, making the clickable area very tall
- The overall visual impression is a large rectangular region, which is the standard pattern for file drop zones

### File: `client/src/pages/Index.tsx`, lines 57-59

The `onSecondaryAction` callback is passed from `Index.tsx`:

```tsx
onSecondaryAction={(priorities) => {
  navigate(`/upload?priorities=${priorities.join(",")}`);
}}
```

This navigates to `/upload` with the selected priorities as query params. This behavior must be preserved exactly.

### The `[ RUN SCAN ]` button (reference style), lines 167-192

This is the existing compact button style that the upload button should match:

```tsx
<button
  type="submit"
  disabled={!value.trim() || isLoading}
  className={cn(
    "w-3/5 border border-primary bg-primary/10 text-primary py-2.5 px-6",
    "uppercase tracking-widest text-xs font-medium",
    "transition-all duration-300",
    "hover:bg-primary hover:text-primary-foreground",
    "disabled:opacity-50 disabled:cursor-not-allowed",
    "relative group"
  )}
>
  {/* Corner brackets */}
  {/* ... */}
  [ run scan ]
</button>
```

Key style properties of the `[ RUN SCAN ]` button:
- `w-3/5` (60% of parent, not full width)
- `border` (1px, not `border-2`)
- `border-primary` with `bg-primary/10`
- `py-2.5 px-6` (compact vertical padding)
- `text-xs` (smaller text)
- `font-medium` (not `font-bold`)
- Wrapped in `<div className="flex justify-center mt-4">` for centering
- Text content rendered as `[ run scan ]` with literal bracket characters

## Target State

Replace the large rectangle with a compact, clearly-clickable button that:

1. Matches the visual language of the `[ RUN SCAN ]` button (compact, bordered, bracket corners)
2. Is slightly more prominent than `[ RUN SCAN ]` since it is the primary CTA (achieved through slightly wider width and/or a filled background, NOT through size)
3. Shows text: `[ UPLOAD CANDIDATE RESUMES ]` (with bracket wrapping, matching the `[ run scan ]` pattern)
4. Moves the subtitle "Batch analyze up to 10 resumes at once" to a small line of text below the button (outside the button element itself), or removes it entirely
5. Preserves the navigation behavior: clicking calls `onSecondaryAction(prioritiesArray())`, which navigates to `/upload?priorities=...`
6. Preserves the "or paste a github url" divider below it

## Implementation Plan

### Step 1: Modify the secondary action button in `TerminalInput.tsx`

**File:** `client/src/components/TerminalInput.tsx`

**What to change:** Replace the button's `className` string (lines 79-86) and its inner content (lines 87-97).

**New className for the button:**

```tsx
className={cn(
  "border border-primary bg-primary/10 text-primary py-2.5 px-8",
  "uppercase tracking-widest text-xs font-medium",
  "transition-all duration-300",
  "hover:bg-primary hover:text-primary-foreground",
  "relative group"
)}
```

Specific class changes from current to target:
| Current | Target | Reason |
|---------|--------|--------|
| `w-full` | _(removed)_ | Button should size to content, not span full width |
| `border-2 border-primary/70` | `border border-primary` | Thinner border, matches `[ RUN SCAN ]` |
| `bg-primary/5` | `bg-primary/10` | Slightly more visible fill, matches `[ RUN SCAN ]` |
| `backdrop-blur-sm` | _(removed)_ | Unnecessary for a compact button |
| `py-5 px-6` | `py-2.5 px-8` | Shorter vertically, wider horizontally for the longer text |
| `text-sm font-bold` | `text-xs font-medium` | Matches `[ RUN SCAN ]` typography |
| `hover:bg-primary/15 hover:border-primary hover:glow-amber` | `hover:bg-primary hover:text-primary-foreground` | Matches `[ RUN SCAN ]` hover: fills solid on hover |

**New inner content for the button:**

Replace the inner `<span>` elements (lines 88-97) with a single text node:

```tsx
[ upload candidate resumes ]
```

This matches the `[ run scan ]` text pattern — literal bracket characters wrapping lowercase text.

Remove the four corner-bracket `<span>` decorations (the `&#9484;` / `&#9488;` / `&#9492;` / `&#9496;` characters on lines 88-91). The `[ ]` in the text content provides sufficient bracket styling, consistent with `[ run scan ]`.

Alternatively, keep the corner bracket decorations and use text content without the `[ ]` wrapper. Either approach is acceptable as long as it matches the `[ RUN SCAN ]` button's visual pattern. Pick ONE approach and be consistent.

**Subtitle handling:**

Move the subtitle text ("Batch analyze up to 10 resumes at once") **outside** the `<button>` element, rendered as a separate `<p>` or `<span>` below it:

```tsx
<p className="text-[10px] text-muted-foreground mt-1.5 text-center tracking-wider">
  Batch analyze up to 10 resumes at once
</p>
```

This keeps the helpful context without making the button itself taller.

### Step 2: Wrap the button in a centering container

The button is no longer `w-full`, so it needs to be centered. Wrap the `<button>` (and its subtitle `<p>`) inside a flex centering container:

```tsx
<div className="flex flex-col items-center">
  <button ...>[ upload candidate resumes ]</button>
  <p className="text-[10px] text-muted-foreground mt-1.5 tracking-wider">
    Batch analyze up to 10 resumes at once
  </p>
</div>
```

### Step 3: Verify the divider is unaffected

The "or paste a github url" divider (lines 103-107) sits inside the same `<div className="mb-6">` wrapper and should remain untouched:

```tsx
<div className="flex items-center gap-3 my-4">
  <div className="flex-1 border-t border-border/50" />
  <span className="text-xs text-muted-foreground uppercase tracking-widest">or paste a github url</span>
  <div className="flex-1 border-t border-border/50" />
</div>
```

No changes needed here.

### Step 4: No changes to `Index.tsx`

`Index.tsx` only passes the `onSecondaryAction` callback prop. No changes are needed in this file. All visual changes are scoped to `TerminalInput.tsx`.

## Complete Modified JSX Block

For maximum clarity, here is the exact JSX that should replace lines 72-108 of `TerminalInput.tsx`:

```tsx
{/* Upload Resumes — prominent CTA */}
{(secondaryAction || onSecondaryAction) && (
  <div className="mb-6">
    {onSecondaryAction ? (
      <div className="flex flex-col items-center">
        <button
          type="button"
          onClick={() => onSecondaryAction(prioritiesArray())}
          className={cn(
            "border border-primary bg-primary/10 text-primary py-2.5 px-8",
            "uppercase tracking-widest text-xs font-medium",
            "transition-all duration-300",
            "hover:bg-primary hover:text-primary-foreground",
            "relative group"
          )}
        >
          <span className="absolute -top-px -left-px text-primary group-hover:text-primary-foreground text-xs">&#9484;</span>
          <span className="absolute -top-px -right-px text-primary group-hover:text-primary-foreground text-xs">&#9488;</span>
          <span className="absolute -bottom-px -left-px text-primary group-hover:text-primary-foreground text-xs">&#9492;</span>
          <span className="absolute -bottom-px -right-px text-primary group-hover:text-primary-foreground text-xs">&#9496;</span>
          [ upload candidate resumes ]
        </button>
        <p className="text-[10px] text-muted-foreground mt-1.5 tracking-wider">
          Batch analyze up to 10 resumes at once
        </p>
      </div>
    ) : (
      secondaryAction
    )}

    <div className="flex items-center gap-3 my-4">
      <div className="flex-1 border-t border-border/50" />
      <span className="text-xs text-muted-foreground uppercase tracking-widest">or paste a github url</span>
      <div className="flex-1 border-t border-border/50" />
    </div>
  </div>
)}
```

## Files to Modify

| File | Change |
|------|--------|
| `client/src/components/TerminalInput.tsx` | Restyle the `onSecondaryAction` button from drop-zone rectangle to compact button (lines 72-108) |

## Files NOT to Modify

| File | Reason |
|------|--------|
| `client/src/pages/Index.tsx` | No changes needed; the `onSecondaryAction` prop interface is unchanged |
| `client/src/pages/UploadPage.tsx` | Out of scope; this spec only affects the landing page CTA |
| Any CSS/Tailwind config files | All styling uses existing Tailwind utility classes |

## Risks & Tradeoffs

### Risk: Button too small, users miss it
The upload CTA is a primary action. Making it too small could hurt discoverability.
**Mitigation:** The button is positioned above the main input area and above a labeled divider ("or paste a github url"), giving it prominent placement. The `bg-primary/10` fill and `border-primary` border provide strong visual contrast. The centering draws the eye.

### Risk: Subtitle text orphaned below the button
Moving the subtitle outside the button means it is no longer part of the clickable area.
**Mitigation:** The subtitle is informational ("Batch analyze up to 10 resumes at once"), not actionable. Users do not need to click on it. The button text itself ("upload candidate resumes") is self-explanatory.

### Rejected Alternatives

| Alternative | Why Rejected |
|-------------|--------------|
| Add drag-and-drop to the landing page | Overcomplicates the landing page. The upload page already handles this well. |
| Remove the CTA entirely and just link in text | Reduces conversion. A clear button is better. |
| Make the button full-width but with dashed border | Still looks like a drop zone. The core issue is the large rectangular area, not just the border style. |
| Move the button below the GitHub input | Changes the visual hierarchy. The upload-resume flow is the primary CTA and should appear first. |

## Testing & Verification

1. **Visual check:** The button should look like a button (compact, single-line text, clear hover state), not like a drop zone (large rectangle)
2. **Click behavior:** Clicking the button navigates to `/upload?priorities=...` with the selected priorities
3. **Hover state:** On hover, the button should fill with the primary color and text should change to `primary-foreground` (matching `[ RUN SCAN ]` behavior)
4. **Divider intact:** The "or paste a github url" divider should still render between the upload button and the GitHub URL input
5. **Layout balance:** The overall landing page should look balanced — the upload button should not dominate or look lost
6. **Mobile responsiveness:** The button should remain centered and tappable on mobile screens. Since it is no longer `w-full`, verify it does not overflow on narrow screens (the `px-8` and long text should still fit within 320px viewports; if not, consider `text-[10px]` on mobile)
7. **Priority passthrough:** The selected priority checkboxes should still be passed correctly when clicking the upload button (test by selecting/deselecting priorities, clicking upload, and checking the URL query params)

## Guardrails for Implementing Agent

- **ASK before assuming** if any requirement is ambiguous. Do not guess.
- Do NOT touch `UploadPage.tsx` -- only modify `TerminalInput.tsx`.
- Do NOT add drag-and-drop functionality to the landing page.
- Do NOT change the `onSecondaryAction` prop interface or how `Index.tsx` calls it.
- Keep the terminal/hacker aesthetic consistent with the rest of the page.
- The button must call `onSecondaryAction(prioritiesArray())`, not handle file uploads directly.
- Use the "Complete Modified JSX Block" section above as the source of truth for the target implementation.
