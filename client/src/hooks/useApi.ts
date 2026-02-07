import { useMutation } from '@tanstack/react-query';
import { api, AnalysisResponse, EvaluateResponse } from '@/services/api';

/**
 * A mutation hook that orchestrates the parallel analysis and evaluation of a repository.
 *
 * @returns A mutation object from tanstack-query.
 *   - `mutate`: A function to trigger the analysis, accepting a `repo_url`.
 *   - `data`: On success, this will be a tuple `[AnalysisResponse, EvaluateResponse]`.
 *   - `isPending`, `isError`, `error`, etc. are also available.
 */
export function useAnalyzeAndEvaluateRepo() {
  return useMutation<[AnalysisResponse, EvaluateResponse], Error, string>({
    mutationFn: (repo_url: string) => {
      // Run both API calls in parallel for efficiency
      return Promise.all([
        api.analyzeRepo(repo_url),
        api.evaluateRepo(repo_url),
      ]);
    },
  });
}
