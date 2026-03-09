import type { AnalysisResponse, EvaluationEvent } from "@/services/api";

export type Tier =
  | "Virgin"
  | "CRACKED"
  | "Vibe Coder"
  | "Enthusiast"
  | "I did a tutorial";

export interface TierResult {
  tier: Tier;
  color: string;
  description: string;
}

const TIER_INFO: Record<Tier, { color: string; description: string }> = {
  Virgin: {
    color: "#a855f7",
    description: "Flawless execution, real impact",
  },
  CRACKED: {
    color: "#22c55e",
    description: "Writes real code, ships real things",
  },
  "Vibe Coder": {
    color: "#ef4444",
    description: "Vibes with AI, ships fast",
  },
  Enthusiast: {
    color: "#3b82f6",
    description: "Shows promise and genuine interest",
  },
  "I did a tutorial": {
    color: "#f59e0b",
    description: "Getting started on the journey",
  },
};

export function getTier(
  analysis: AnalysisResponse,
  evaluation: EvaluationEvent | null
): TierResult {
  const verdict = analysis.verdict.type;
  const codeQuality = analysis.code_quality.score;
  const badPractices = analysis.bad_practices.score;
  const standout = evaluation?.standout_features ?? [];
  const solvesReal =
    evaluation?.business_value?.solves_real_problem === true;
  const isSenior = verdict === "Senior";


  // Priority 1: Virgin (CRACKED + pristine code)
  if (
    isSenior &&
    solvesReal &&
    standout.length > 0 &&
    codeQuality >= 80 &&
    badPractices <= 20
  ) {
    return { tier: "Virgin", ...TIER_INFO["Virgin"] };
  }

  // Priority 2: CRACKED
  if (isSenior && solvesReal && standout.length > 0) {
    return { tier: "CRACKED", ...TIER_INFO["CRACKED"] };
  }

  // Priority 3: Vibe Coder (high AI usage)
  if (analysis.ai_slop.score >= 90) {
    return { tier: "Vibe Coder", ...TIER_INFO["Vibe Coder"] };
  }

  // Priority 4: Enthusiast
  if (standout.length > 0 && analysis.ai_slop.score < 90 && !isSenior) {
    return { tier: "Enthusiast", ...TIER_INFO["Enthusiast"] };
  }

  // Priority 5: Fallback
  return { tier: "I did a tutorial", ...TIER_INFO["I did a tutorial"] };
}

export function deriveTraits(
  analysis: AnalysisResponse,
  evaluation: EvaluationEvent | null
): string[] {
  const traits: string[] = [];

  // From standout features (most specific)
  if (evaluation?.standout_features) {
    for (const f of evaluation.standout_features.slice(0, 2)) {
      traits.push(f);
    }
  }

  // From scores
  if (analysis.code_quality.score >= 80) {
    traits.push("High Code Quality");
  } else if (analysis.code_quality.score >= 60) {
    traits.push("Decent Code Quality");
  }

  if (analysis.bad_practices.score <= 15) {
    traits.push("Clean Practices");
  }

  if (analysis.code_quality.readme_quality >= 80) {
    traits.push("Strong Documentation");
  }

  if (analysis.code_quality.dependency_health >= 80) {
    traits.push("Healthy Dependencies");
  }

  if (evaluation?.business_value?.solves_real_problem) {
    traits.push("Solves Real Problems");
  }

  // Cap at 4 traits
  return traits.slice(0, 4);
}
