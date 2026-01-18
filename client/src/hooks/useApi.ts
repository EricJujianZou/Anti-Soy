import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, UserData } from '@/services/api';

export function useUserMetadata(username: string | null) {
  return useQuery({
    queryKey: ['user', username],
    queryFn: () => api.fetchUserMetadata(`https://github.com/${username}`),
    enabled: !!username,
  });
}

export function useCreateUserMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (username: string) => api.fetchUserMetadata(`https://github.com/${username}`),
    onSuccess: (data) => {
      queryClient.setQueryData(['user', data.username], data);
    },
  });
}

export function useAnalyzeRepo() {
  return useMutation({
    mutationFn: (repoLink: string) => api.analyzeRepo(repoLink),
  });
}

export function getCachedUserData(queryClient: ReturnType<typeof useQueryClient>, username: string): UserData | undefined {
  return queryClient.getQueryData(['user', username]);
}
