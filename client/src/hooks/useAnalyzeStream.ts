import { useState, useCallback, useRef } from "react";
import {
  analyzeRepoStream,
  type AnalysisResponse,
  type EvaluationEvent,
  type InterviewQuestion,
} from "@/services/api";

export interface StreamState {
  isStreaming: boolean;
  error: string | null;
  analysis: AnalysisResponse | null;
  evaluation: EvaluationEvent | null;
  questions: InterviewQuestion[] | null;
  questionsError: string | null;
  isDone: boolean;
}

const initialState: StreamState = {
  isStreaming: false,
  error: null,
  analysis: null,
  evaluation: null,
  questions: null,
  questionsError: null,
  isDone: false,
};

export function useAnalyzeStream() {
  const [state, setState] = useState<StreamState>(initialState);
  const streamingRef = useRef(false);

  const startStream = useCallback((repoUrl: string) => {
    if (streamingRef.current) return;
    streamingRef.current = true;

    setState({ ...initialState, isStreaming: true });

    analyzeRepoStream(repoUrl, {
      onAnalysis: (data) => {
        setState((prev) => ({ ...prev, analysis: data }));
      },
      onEvaluation: (data) => {
        setState((prev) => ({ ...prev, evaluation: data }));
      },
      onQuestions: (data) => {
        setState((prev) => ({
          ...prev,
          questions: data.interview_questions,
          questionsError: data.error ?? null,
        }));
      },
      onDone: () => {
        gtag("event", "analysis_completed", {
          event_category: "engagement",
          repo_url: repoUrl,
        });
        setState((prev) => ({ ...prev, isStreaming: false, isDone: true }));
        streamingRef.current = false;
      },
      onError: (message) => {
        gtag("event", "analysis_failed", {
          event_category: "engagement",
          repo_url: repoUrl,
          error_message: message,
        });
        setState((prev) => ({ ...prev, isStreaming: false, error: message }));
        streamingRef.current = false;
      },
    }).catch((err) => {
      const errorMsg = err instanceof Error ? err.message : "Connection failed";
      gtag("event", "analysis_failed", {
        event_category: "engagement",
        repo_url: repoUrl,
        error_message: errorMsg,
      });
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        error: errorMsg,
      }));
      streamingRef.current = false;
    });
  }, []);

  return { ...state, startStream };
}
