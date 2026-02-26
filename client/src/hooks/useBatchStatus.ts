import { useState, useEffect, useRef } from "react";
import { getBatchStatus, type BatchStatusResponse } from "@/services/batchApi";

export function useBatchStatus(batchId: string) {
  const [data, setData] = useState<BatchStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!batchId) return;

    const fetchStatus = async () => {
      try {
        const response = await getBatchStatus(batchId);
        setData(response);
        setIsLoading(false);
        setError(null);

        // Stop polling if completed or failed
        if (response.status === "completed" || response.status === "failed") {
          stopPolling();
        }
      } catch (err) {
        if (err instanceof Error && err.message === "Batch not found.") {
          setError("Batch not found.");
          stopPolling();
        } else {
          // Log and continue polling for transient errors
          console.error("Polling error:", err);
        }
      }
    };

    const startPolling = () => {
      if (pollingIntervalRef.current) return;
      
      // Initial fetch
      fetchStatus();
      
      pollingIntervalRef.current = window.setInterval(() => {
        // Only fetch if tab is visible
        if (document.visibilityState === "visible") {
          fetchStatus();
        }
      }, 3000);
    };

    const stopPolling = () => {
      if (pollingIntervalRef.current) {
        window.clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        // If it was already completed/failed, don't restart
        if (data?.status !== "completed" && data?.status !== "failed") {
          fetchStatus();
        }
      }
    };

    startPolling();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [batchId, data?.status]);

  return { data, isLoading, error };
}
