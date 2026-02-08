// =============================================================================
// API CONFIGURATION
// =============================================================================
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

// =============================================================================
// TYPE DEFINITIONS (from server/v2/schemas.py)
// =============================================================================

export type Severity = "critical" | "warning" | "info";
export type Confidence = "low" | "medium" | "high";
export type ProjectType = "real_problem" | "tutorial" | "portfolio_demo" | "learning_exercise" | "utility_tool";

export interface Finding {
  type: string;
  severity: Severity;
  file: string;
  line: number;
  snippet: string;
  explanation: string;
}

export interface PositiveSignal {
  type: string;
  file?: string | null;
  explanation: string;
}

export interface FileAnalyzed {
  path: string;
  importance_score: number;
  loc: number;
}

export interface RepoInfo {
  url: string;
  name: string;
  owner: string;
  languages: Record<string, number>;
  analyzed_at: string; // ISO datetime string
}

export interface Verdict {
  type: string;
  confidence: number;
}

export interface StyleFeatures {
  function_naming_consistency: number;
  variable_naming_consistency: number;
  class_naming_consistency: number;
  constant_naming_consistency: number;
  indentation_consistency: number;
  avg_function_length: number;
  avg_nesting_depth: number;
  comment_ratio: number;
  avg_function_name_length: number;
  avg_variable_name_length: number;
  max_function_length: number;
  max_nesting_depth: number;
  docstring_coverage: number;
  redundant_comment_count: number;
}

export interface AISlop {
  score: number;
  confidence: Confidence;
  style_features: StyleFeatures;
  negative_ai_signals: Finding[];
  positive_ai_signals: PositiveSignal[];
}

export interface BadPractices {
  score: number;
  security_issues: number;
  robustness_issues: number;
  hygiene_issues: number;
  findings: Finding[];
}

export interface CodeQuality {
  score: number;
  files_organized: number;
  test_coverage: number;
  readme_quality: number;
  error_handling: number;
  logging_quality: number;
  dependency_health: number;
  findings: Finding[];
}

export interface AnalysisResponse {
  repo: RepoInfo;
  verdict: Verdict;
  ai_slop: AISlop;
  bad_practices: BadPractices;
  code_quality: CodeQuality;
  files_analyzed: FileAnalyzed[];
}

export interface InterviewQuestion {
  question: string;
  based_on: string;
  probes: string;
  category: string;
}

export interface BusinessValue {
  solves_real_problem: boolean;
  project_type: ProjectType;
  project_description: string;
  originality_assessment: string;
  project_summary: string;
}

export interface EvaluateResponse {
  repo_id: number;
  repo_url: string;
  is_rejected: boolean;
  rejection_reason?: string | null;
  business_value: BusinessValue;
  standout_features: string[];
  interview_questions: InterviewQuestion[];
}


// =============================================================================
// SSE STREAMING TYPES
// =============================================================================

export interface EvaluationEvent {
  business_value: BusinessValue | null;
  standout_features: string[];
  is_rejected: boolean;
  rejection_reason?: string | null;
}

export interface QuestionsEvent {
  interview_questions: InterviewQuestion[];
  error?: string;
}

export interface StreamCallbacks {
  onAnalysis: (data: AnalysisResponse) => void;
  onEvaluation: (data: EvaluationEvent) => void;
  onQuestions: (data: QuestionsEvent) => void;
  onDone: () => void;
  onError: (message: string, step: string) => void;
}


// =============================================================================
// API FUNCTIONS
// =============================================================================

export const api = {
  /**
   * Triggers the static analysis pipeline (/analyze).
   * Returns detailed metrics on AI slop, bad practices, and code quality.
   */
  analyzeRepo: async (repo_url: string): Promise<AnalysisResponse> => {
    const res = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url }),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to analyze repo' }));
      throw new Error(error.detail);
    }
    return res.json();
  },

  /**
   * Triggers the full evaluation pipeline (/evaluate), including LLM analysis.
   * Returns business value, interview questions, and reject status.
   */
  evaluateRepo: async (repo_url: string): Promise<EvaluateResponse> => {
    const res = await fetch(`${API_BASE_URL}/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url }),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Failed to evaluate repo' }));
      throw new Error(error.detail);
    }
    return res.json();
  },
};


/**
 * SSE streaming endpoint — progressive analysis.
 * Uses fetch + ReadableStream (can't use EventSource with POST).
 */
export async function analyzeRepoStream(
  repo_url: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/analyze-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to start analysis" }));
    callbacks.onError(error.detail, "http");
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("Streaming not supported", "http");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE messages are separated by double newlines
    const messages = buffer.split("\n\n");
    // Last element may be incomplete — keep it in buffer
    buffer = messages.pop() ?? "";

    for (const message of messages) {
      if (!message.trim()) continue;

      let eventType = "";
      let data = "";

      for (const line of message.split("\n")) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          data = line.slice(6);
        }
      }

      if (!eventType || !data) continue;

      try {
        const parsed = JSON.parse(data);

        switch (eventType) {
          case "analysis":
            callbacks.onAnalysis(parsed);
            break;
          case "evaluation":
            callbacks.onEvaluation(parsed);
            break;
          case "questions":
            callbacks.onQuestions(parsed);
            break;
          case "done":
            callbacks.onDone();
            break;
          case "error":
            callbacks.onError(parsed.message ?? "Unknown error", parsed.step ?? "unknown");
            break;
        }
      } catch {
        callbacks.onError("Failed to parse server response", "parse");
      }
    }
  }
}
