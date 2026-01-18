const API_BASE_URL = 'http://localhost:8000';

export interface RepoMetric {
  score: number;
  comment: string;
}

export interface RepoAnalysis {
  status: string;
  repo_id: number;
  repo_link: string;
  files_organized: RepoMetric;
  test_suites: RepoMetric;
  readme: RepoMetric;
  api_keys: RepoMetric;
  error_handling: RepoMetric;
  comments: RepoMetric;
  print_or_logging: RepoMetric;
  dependencies: RepoMetric;
  commit_density: RepoMetric;
  commit_lines: RepoMetric;
  concurrency: RepoMetric;
  caching: RepoMetric;
  solves_real_problem: RepoMetric;
  aligns_company: RepoMetric;
}

export interface UserRepo {
  id: number;
  github_link: string;
  stars: number;
  is_open_source_project: boolean;
  prs_merged: number;
  languages: string; // JSON string
}

export interface UserData {
  id: number;
  username: string;
  github_link: string;
  repos: UserRepo[];
}

export const api = {
  fetchUserMetadata: async (githubLink: string): Promise<UserData> => {
    const res = await fetch(`${API_BASE_URL}/metadata?user=${encodeURIComponent(githubLink)}`, {
      method: 'PUT',
    });
    if (!res.ok) throw new Error('Failed to fetch user');
    return res.json();
  },

  analyzeRepo: async (repoLink: string): Promise<RepoAnalysis> => {
    const res = await fetch(`${API_BASE_URL}/repo?repo=${encodeURIComponent(repoLink)}`, {
      method: 'PUT',
    });
    if (!res.ok) throw new Error('Failed to analyze repo');
    return res.json();
  },
};
