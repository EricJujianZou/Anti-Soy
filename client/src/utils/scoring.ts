import { RepoAnalysis } from "@/services/api";

type MetricSignal = {
  label: string;
  value: string;
  tone: "good" | "warn" | "bad" | "neutral";
};

type RadarDataPoint = {
  category: string;
  value: number;
  fullMark: number;
};

type AIUsageLevel = {
  level: "Low" | "Medium" | "High";
  score: number;
};

/**
 * Compute overall repository score from analysis metrics
 */
export function computeOverallScore(analysis: RepoAnalysis): number {
  const weights = {
    files_organized: 0.1,
    test_suites: 0.15,
    readme: 0.1,
    api_keys: 0.1,
    error_handling: 0.15,
    comments: 0.05,
    print_or_logging: 0.05,
    dependencies: 0.05,
    commit_density: 0.1,
    commit_lines: 0.05,
    concurrency: 0.05,
    caching: 0.05,
  };

  let totalScore = 0;
  let totalWeight = 0;

  for (const [key, weight] of Object.entries(weights)) {
    const metric = analysis[key as keyof typeof weights];
    if (metric && typeof metric.score === "number") {
      totalScore += metric.score * weight;
      totalWeight += weight;
    }
  }

  return totalWeight > 0 ? Math.round(totalScore / totalWeight) : 0;
}

/**
 * Compute radar chart data for visualization
 */
export function computeRadarData(analysis: RepoAnalysis): RadarDataPoint[] {
  return [
    { category: "Organization", value: analysis.files_organized.score, fullMark: 100 },
    { category: "Testing", value: analysis.test_suites.score, fullMark: 100 },
    { category: "Documentation", value: analysis.readme.score, fullMark: 100 },
    { category: "Security", value: analysis.api_keys.score, fullMark: 100 },
    { category: "Error Handling", value: analysis.error_handling.score, fullMark: 100 },
    { category: "Code Quality", value: analysis.comments.score, fullMark: 100 },
  ];
}

/**
 * Compute AI usage level based on comments and commit patterns
 */
export function computeAIUsageLevel(analysis: RepoAnalysis): AIUsageLevel {
  // Lower comments score + boilerplate patterns could indicate AI usage
  const commentsScore = analysis.comments.score;
  const commitLinesScore = analysis.commit_lines.score;
  
  // Heuristic: very uniform commit sizes and generic comments might indicate AI
  const aiIndicator = (100 - commentsScore) * 0.5 + (100 - commitLinesScore) * 0.5;
  
  if (aiIndicator >= 60) {
    return { level: "High", score: aiIndicator };
  } else if (aiIndicator >= 30) {
    return { level: "Medium", score: aiIndicator };
  }
  return { level: "Low", score: aiIndicator };
}

/**
 * Generate strengths based on high-scoring metrics
 */
export function generateStrengths(analysis: RepoAnalysis): string[] {
  const strengths: string[] = [];

  if (analysis.files_organized.score >= 70) {
    strengths.push("Well-organized file structure");
  }
  if (analysis.test_suites.score >= 70) {
    strengths.push("Good test coverage");
  }
  if (analysis.readme.score >= 70) {
    strengths.push("Comprehensive documentation");
  }
  if (analysis.api_keys.score >= 80) {
    strengths.push("Secure API key handling");
  }
  if (analysis.error_handling.score >= 70) {
    strengths.push("Robust error handling");
  }
  if (analysis.commit_density.score >= 70) {
    strengths.push("Consistent commit history");
  }
  if (analysis.concurrency.score >= 70) {
    strengths.push("Good concurrency patterns");
  }
  if (analysis.caching.score >= 70) {
    strengths.push("Effective caching strategy");
  }
  if (analysis.dependencies.score >= 70) {
    strengths.push("Well-managed dependencies");
  }

  return strengths.length > 0 ? strengths : ["Repository analyzed successfully"];
}

/**
 * Generate red flags based on low-scoring metrics
 */
export function generateRedFlags(analysis: RepoAnalysis): string[] {
  const redFlags: string[] = [];

  if (analysis.api_keys.score < 50) {
    redFlags.push("Potential API key exposure risks");
  }
  if (analysis.test_suites.score < 30) {
    redFlags.push("Insufficient test coverage");
  }
  if (analysis.error_handling.score < 40) {
    redFlags.push("Weak error handling");
  }
  if (analysis.readme.score < 30) {
    redFlags.push("Missing or incomplete documentation");
  }
  if (analysis.files_organized.score < 40) {
    redFlags.push("Poor file organization");
  }
  if (analysis.commit_density.score < 30) {
    redFlags.push("Irregular commit patterns");
  }
  if (analysis.dependencies.score < 40) {
    redFlags.push("Dependency management issues");
  }

  return redFlags;
}

/**
 * Generate improvement suggestions
 */
export function generateSuggestions(analysis: RepoAnalysis): string[] {
  const suggestions: string[] = [];

  if (analysis.test_suites.score < 70) {
    suggestions.push("Add more unit and integration tests");
  }
  if (analysis.readme.score < 70) {
    suggestions.push("Improve README with setup instructions and examples");
  }
  if (analysis.error_handling.score < 70) {
    suggestions.push("Implement more comprehensive error handling");
  }
  if (analysis.comments.score < 50) {
    suggestions.push("Add meaningful code comments for complex logic");
  }
  if (analysis.api_keys.score < 80) {
    suggestions.push("Review and secure sensitive configuration");
  }
  if (analysis.concurrency.score < 50) {
    suggestions.push("Consider async patterns for better performance");
  }
  if (analysis.caching.score < 50) {
    suggestions.push("Implement caching for frequently accessed data");
  }
  if (analysis.files_organized.score < 60) {
    suggestions.push("Reorganize files into clearer directory structure");
  }

  return suggestions.length > 0 ? suggestions : ["Keep up the good work!"];
}

/**
 * Generate production readiness signals
 */
export function generateProductionSignals(analysis: RepoAnalysis): MetricSignal[] {
  const signals: MetricSignal[] = [];

  // Error handling signal
  const errorScore = analysis.error_handling.score;
  signals.push({
    label: "Error Handling",
    value: errorScore >= 70 ? "Robust" : errorScore >= 40 ? "Basic" : "Needs Work",
    tone: errorScore >= 70 ? "good" : errorScore >= 40 ? "warn" : "bad",
  });

  // Logging signal
  const loggingScore = analysis.print_or_logging.score;
  signals.push({
    label: "Logging",
    value: loggingScore >= 70 ? "Production-ready" : loggingScore >= 40 ? "Basic" : "Debug only",
    tone: loggingScore >= 70 ? "good" : loggingScore >= 40 ? "warn" : "bad",
  });

  // Dependencies signal
  const depsScore = analysis.dependencies.score;
  signals.push({
    label: "Dependencies",
    value: depsScore >= 70 ? "Well managed" : depsScore >= 40 ? "Acceptable" : "Review needed",
    tone: depsScore >= 70 ? "good" : depsScore >= 40 ? "warn" : "bad",
  });

  return signals;
}

/**
 * Generate AI usage signals
 */
export function generateAIUsageSignals(analysis: RepoAnalysis): MetricSignal[] {
  const signals: MetricSignal[] = [];

  // Comment quality signal
  const commentsScore = analysis.comments.score;
  signals.push({
    label: "Comment Quality",
    value: commentsScore >= 70 ? "Human-like" : commentsScore >= 40 ? "Mixed" : "Generic",
    tone: commentsScore >= 70 ? "good" : commentsScore >= 40 ? "neutral" : "warn",
  });

  // Commit patterns signal
  const commitLinesScore = analysis.commit_lines.score;
  signals.push({
    label: "Commit Patterns",
    value: commitLinesScore >= 70 ? "Natural" : commitLinesScore >= 40 ? "Mixed" : "Uniform",
    tone: commitLinesScore >= 70 ? "good" : commitLinesScore >= 40 ? "neutral" : "warn",
  });

  // Commit density signal
  const commitDensityScore = analysis.commit_density.score;
  signals.push({
    label: "Commit Frequency",
    value: commitDensityScore >= 70 ? "Regular" : commitDensityScore >= 40 ? "Moderate" : "Sparse",
    tone: commitDensityScore >= 70 ? "good" : commitDensityScore >= 40 ? "neutral" : "warn",
  });

  return signals;
}

/**
 * Compute production readiness score
 */
export function computeProductionReadinessScore(analysis: RepoAnalysis): number {
  const weights = {
    error_handling: 0.3,
    test_suites: 0.25,
    api_keys: 0.2,
    print_or_logging: 0.15,
    dependencies: 0.1,
  };

  let totalScore = 0;
  for (const [key, weight] of Object.entries(weights)) {
    const metric = analysis[key as keyof typeof weights];
    if (metric && typeof metric.score === "number") {
      totalScore += metric.score * weight;
    }
  }

  return Math.round(totalScore);
}

/**
 * Compute scalability score
 */
export function computeScalabilityScore(analysis: RepoAnalysis): number {
  const weights = {
    concurrency: 0.35,
    caching: 0.35,
    files_organized: 0.15,
    dependencies: 0.15,
  };

  let totalScore = 0;
  for (const [key, weight] of Object.entries(weights)) {
    const metric = analysis[key as keyof typeof weights];
    if (metric && typeof metric.score === "number") {
      totalScore += metric.score * weight;
    }
  }

  return Math.round(totalScore);
}

/**
 * Generate AI-specific suggestions
 */
export function generateAISuggestions(analysis: RepoAnalysis): string[] {
  const suggestions: string[] = [];
  const aiUsage = computeAIUsageLevel(analysis);

  if (aiUsage.level === "High") {
    suggestions.push("Consider adding more personalized code comments");
    suggestions.push("Vary commit message styles and sizes");
    suggestions.push("Add inline documentation explaining design decisions");
  } else if (aiUsage.level === "Medium") {
    suggestions.push("Review auto-generated code for optimization opportunities");
  }

  if (analysis.comments.score < 50) {
    suggestions.push("Add context-specific comments for complex algorithms");
  }

  return suggestions;
}
