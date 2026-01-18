import { useSearchParams, Link } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { RepositoryCard, Repository } from "@/components/RepositoryCard";
import { AsciiPanel } from "@/components/AsciiPanel";
import { useUserMetadata } from "@/hooks/useApi";
import { UserRepo } from "@/services/api";

// Helper to get primary language from languages JSON string
function getPrimaryLanguage(languagesJson: string): { name: string; color: string } {
  const languageColors: Record<string, string> = {
    Python: "#3572A5",
    TypeScript: "#3178c6",
    JavaScript: "#f1e05a",
    Go: "#00ADD8",
    Rust: "#dea584",
    Java: "#b07219",
    C: "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    Ruby: "#701516",
    PHP: "#4F5D95",
    Swift: "#F05138",
    Kotlin: "#A97BFF",
    Scala: "#c22d40",
    Shell: "#89e051",
    HTML: "#e34c26",
    CSS: "#563d7c",
    SCSS: "#c6538c",
    Vue: "#41b883",
  };

  try {
    const languages = JSON.parse(languagesJson);
    const entries = Object.entries(languages) as [string, number][];
    if (entries.length === 0) {
      return { name: "Unknown", color: "#808080" };
    }
    // Sort by bytes descending and get the first one
    entries.sort((a, b) => b[1] - a[1]);
    const primaryLang = entries[0][0];
    return {
      name: primaryLang,
      color: languageColors[primaryLang] || "#808080",
    };
  } catch {
    return { name: "Unknown", color: "#808080" };
  }
}

// Helper to extract repo name from github link
function getRepoName(githubLink: string): string {
  const parts = githubLink.replace(/\/$/, "").split("/");
  return parts[parts.length - 1] || "Unknown";
}

// Map UserRepo from API to Repository for the card component
function mapUserRepoToRepository(repo: UserRepo, index: number): Repository {
  const { name: language, color: languageColor } = getPrimaryLanguage(repo.languages);

  return {
    id: repo.id.toString(),
    name: getRepoName(repo.github_link),
    description: `${repo.is_open_source_project ? "Open source project" : "Repository"} with ${repo.prs_merged} PRs merged`,
    language,
    languageColor,
    stars: repo.stars,
    forks: 0, // Not provided by API
    lastUpdated: "Recently",
    isPrivate: !repo.is_open_source_project,
    // Store the full github link for later use
    githubLink: repo.github_link,
  };
}

const Repositories = () => {
  const [searchParams] = useSearchParams();
  const username = searchParams.get("user");

  const { data: userData, isLoading, isError } = useUserMetadata(username);

  // Map repos from API to display format
  const repositories: Repository[] = userData?.repos
    ? userData.repos.map((repo, idx) => mapUserRepoToRepository(repo, idx))
    : [];

  const totalStars = repositories.reduce((sum, repo) => sum + repo.stars, 0);
  const totalForks = repositories.reduce((sum, repo) => sum + repo.forks, 0);

  if (isLoading) {
    return (
      <GridBackground>
        <Header />
        <main className="container mx-auto px-4 py-12">
          <div className="flex flex-col items-center justify-center min-h-[70vh]">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-foreground mb-4">
                Loading repositories...
              </h2>
              <div className="animate-pulse text-primary">
                <span className="glyph-spinner text-4xl">⟳</span>
              </div>
            </div>
          </div>
        </main>
      </GridBackground>
    );
  }

  if (isError || !userData) {
    return (
      <GridBackground>
        <Header />
        <main className="container mx-auto px-4 py-12">
          <div className="flex flex-col items-center justify-center min-h-[70vh]">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-foreground mb-4">
                Failed to load repositories
              </h2>
              <p className="text-muted-foreground mb-4">
                Could not fetch data for user: {username}
              </p>
              <Link
                to="/"
                className="text-primary hover:underline"
              >
                ← Back to home
              </Link>
            </div>
          </div>
        </main>
      </GridBackground>
    );
  }

  return (
    <GridBackground>
      <Header />

      <main className="container mx-auto px-4 py-12">
        <div className="animate-fade-in-up">
          {/* Page Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Link
                  to="/"
                  className="text-muted-foreground hover:text-foreground transition-colors text-sm"
                >
                  ← Back
                </Link>
                <span className="text-muted-foreground">/</span>
                <h1 className="text-2xl font-bold text-foreground">
                  <span className="text-primary text-glow">@{userData.username}</span>'s Repositories
                </h1>
              </div>
              <p className="text-sm text-muted-foreground">
                {repositories.length} repositories found
              </p>
            </div>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <AsciiPanel variant="highlight">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Repositories</span>
                <span className="text-2xl font-bold text-primary">{repositories.length}</span>
              </div>
            </AsciiPanel>
            <AsciiPanel>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total Stars</span>
                <span className="text-2xl font-bold text-foreground">{totalStars.toLocaleString()}</span>
              </div>
            </AsciiPanel>
            <AsciiPanel>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total PRs Merged</span>
                <span className="text-2xl font-bold text-foreground">
                  {userData.repos.reduce((sum, r) => sum + r.prs_merged, 0)}
                </span>
              </div>
            </AsciiPanel>
          </div>

          {/* Repository List */}
          {repositories.length > 0 ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-primary">▸</span>
                <h2 className="text-sm text-muted-foreground uppercase tracking-widest">
                  Repository List
                </h2>
                <div className="flex-1 h-px bg-border ml-2" />
              </div>

              <div className="grid grid-cols-1 gap-4">
                {repositories.map((repo, index) => (
                  <RepositoryCard
                    key={repo.id}
                    repository={repo}
                    index={index}
                    className="animate-fade-in-up"
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-12">
              <p className="text-muted-foreground">No repositories found for this user.</p>
            </div>
          )}

          {/* Footer Note */}
          <div className="mt-8 text-center">
            <p className="text-xs text-muted-foreground">
              Click on any repository to view detailed analysis
            </p>
          </div>
        </div>
      </main>

      <footer className="border-t border-border bg-card/30 mt-auto">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>© 2025 Anti-Soy</span>
            <span className="flex items-center gap-2">
              <span className="text-primary pulse-glow">●</span>
              System Operational
            </span>
          </div>
        </div>
      </footer>
    </GridBackground>
  );
};

export default Repositories;
