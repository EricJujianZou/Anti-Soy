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
        setState((prev) => ({ ...prev, isStreaming: false, isDone: true }));
        streamingRef.current = false;
      },
      onError: (message) => {
        setState((prev) => ({ ...prev, isStreaming: false, error: message }));
        streamingRef.current = false;
      },
    }).catch((err) => {
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        error: err instanceof Error ? err.message : "Connection failed",
      }));
      streamingRef.current = false;
    });
  }, []);

  return { ...state, startStream };
}
