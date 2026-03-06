const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");
import type { PriorityKey } from "./api";

export interface BatchVerdict {
  type: string;
  confidence: number;
}

export interface BatchItemStatus {
  id: number;
  position: number;
  filename: string;
  candidate_name?: string | null;
  candidate_university?: string | null;
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

export async function uploadBatch(files: File[], priorities?: PriorityKey[], useGenericQuestions?: boolean): Promise<{ batch_id: string }> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("resumes", file);
  });

  if (priorities && priorities.length > 0) {
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
