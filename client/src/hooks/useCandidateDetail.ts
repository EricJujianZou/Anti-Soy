import { useQuery } from "@tanstack/react-query";
import { getCandidateDetail, type CandidateDetailResponse } from "@/services/batchApi";

export function useCandidateDetail(batchId: string, itemId: string) {
  return useQuery<CandidateDetailResponse, Error>({
    queryKey: ["candidateDetail", batchId, itemId],
    queryFn: () => getCandidateDetail(batchId, Number(itemId)),
    enabled: Boolean(batchId && itemId),
    retry: 0,
    staleTime: 5 * 60 * 1000, // 5 min — analysis results don't change
  });
}
