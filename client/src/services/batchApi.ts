const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");
import type { PriorityKey, ScoringConfig, AnalysisResponse, EvaluateResponse, InterviewQuestion } from "./api";

export interface BatchVerdict {
  type: string;
  confidence: number;
}

export interface BatchItemStatus {
  id: number;
  position: number;
  filename: string;
  candidate_name?: string | null;
  repo_url?: string | null;
  status: "pending" | "running" | "completed" | "error";
  error_message?: string | null;
  repo_id?: number | null;
  verdict?: BatchVerdict | null;
  standout_features?: string[];
  overall_score?: number | null;
}

export interface BatchStatusResponse {
  batch_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  total_items: number;
  completed_items: number;
  items: BatchItemStatus[];
  priorities?: PriorityKey[];
}

export async function uploadBatch(
  files: File[],
  scoringConfig?: ScoringConfig,
  useGenericQuestions?: boolean,
  // Legacy param — kept for backward compat but ignored when scoringConfig is provided
  priorities?: PriorityKey[],
): Promise<{ batch_id: string }> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("resumes", file);
  });

  if (scoringConfig) {
    formData.append("scoring_config", JSON.stringify(scoringConfig));
  } else if (priorities && priorities.length > 0) {
    // Legacy fallback
    formData.append("priorities", JSON.stringify(priorities));
  }

  if (useGenericQuestions) {
    formData.append("use_generic_questions", "true");
  }

  const res = await fetch(`${API_BASE_URL}/batch/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to upload batch" }));
    throw new Error(error.detail || "Upload failed");
  }

  return res.json();
}

export async function getBatchStatus(batchId: string): Promise<BatchStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/batch/${batchId}/status`);

  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Batch not found.");
    }
    const error = await res.json().catch(() => ({ detail: "Failed to get batch status" }));
    throw new Error(error.detail || "Failed to get batch status");
  }

  return res.json();
}


// =============================================================================
// CANDIDATE DETAIL
// =============================================================================

export interface CandidateRepoDetail {
  repo_id: number;
  repo_url: string;
  repo_name: string;
  overall_score: number;
  analysis: AnalysisResponse;
  evaluation: EvaluateResponse;
}

export interface TechStackLanguage {
  language: string;
  total_projects: number;
  hand_coded: number;   // repos where ai_slop_score < 60
  vibe_coded: number;   // repos where ai_slop_score >= 60
  project_names: string[];
}

export interface CandidateDetailResponse {
  item_id: number;
  candidate_name: string;
  github_profile_url: string | null;
  overall_score: number;
  repos: CandidateRepoDetail[];
  interview_questions: InterviewQuestion[] | null;  // null = not yet generated
  tech_stack_breakdown?: TechStackLanguage[] | null;
}

export async function getCandidateDetail(
  batchId: string,
  itemId: number,
): Promise<CandidateDetailResponse> {
  const res = await fetch(`${API_BASE_URL}/batch/${batchId}/items/${itemId}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to fetch candidate detail" }));
    throw new Error(error.detail || "Failed to fetch candidate detail");
  }
  return res.json();
}

export async function generateBatchInterviewQuestions(
  batchId: string,
  itemId: number,
): Promise<{ interview_questions: InterviewQuestion[] }> {
  const res = await fetch(`${API_BASE_URL}/batch/${batchId}/items/${itemId}/interview-questions`, {
    method: "POST",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Failed to generate questions" }));
    throw new Error(error.detail || "Failed to generate questions");
  }
  return res.json();
}
