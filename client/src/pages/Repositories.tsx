import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { RepositoryCard, Repository } from "@/components/RepositoryCard";
import { AsciiPanel } from "@/components/AsciiPanel";
import { Link } from "react-router-dom";

// Mock data for the top 5 most recent repositories
const mockRepositories: Repository[] = [
  {
    id: "neural-search-engine",
    name: "neural-search-engine",
    description: "A semantic search engine powered by transformer embeddings and FAISS for lightning-fast similarity matching across large document corpora.",
    language: "Python",
    languageColor: "#3572A5",
    stars: 847,
    forks: 124,
    lastUpdated: "2 days ago",
    isPrivate: false,
  },
  {
    id: "react-terminal-ui",
    name: "react-terminal-ui",
    description: "A customizable terminal emulator component for React applications with command history, autocomplete, and theming support.",
    language: "TypeScript",
    languageColor: "#3178c6",
    stars: 1243,
    forks: 89,
    lastUpdated: "5 days ago",
    isPrivate: false,
  },
  {
    id: "cloud-infra-toolkit",
    name: "cloud-infra-toolkit",
    description: "Infrastructure as Code templates and utilities for deploying scalable microservices on AWS, GCP, and Azure.",
    language: "Go",
    languageColor: "#00ADD8",
    stars: 432,
    forks: 67,
    lastUpdated: "1 week ago",
    isPrivate: false,
  },
  {
    id: "ml-pipeline-orchestrator",
    name: "ml-pipeline-orchestrator",
    description: "End-to-end ML pipeline management with experiment tracking, model versioning, and automated deployment workflows.",
    language: "Python",
    languageColor: "#3572A5",
    stars: 289,
    forks: 41,
    lastUpdated: "2 weeks ago",
    isPrivate: true,
  },
  {
    id: "rust-crypto-lib",
    name: "rust-crypto-lib",
    description: "High-performance cryptographic primitives implemented in Rust with zero-copy operations and constant-time guarantees.",
    language: "Rust",
    languageColor: "#dea584",
    stars: 567,
    forks: 78,
    lastUpdated: "3 weeks ago",
    isPrivate: false,
  },
];

const Repositories = () => {
  const totalStars = mockRepositories.reduce((sum, repo) => sum + repo.stars, 0);
  const totalForks = mockRepositories.reduce((sum, repo) => sum + repo.forks, 0);

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
                  Recent <span className="text-primary text-glow">Repositories</span>
                </h1>
              </div>
              <p className="text-sm text-muted-foreground">
                Your top 5 most recently updated repositories
              </p>
            </div>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <AsciiPanel variant="highlight">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Repositories</span>
                <span className="text-2xl font-bold text-primary">{mockRepositories.length}</span>
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
                <span className="text-sm text-muted-foreground">Total Forks</span>
                <span className="text-2xl font-bold text-foreground">{totalForks.toLocaleString()}</span>
              </div>
            </AsciiPanel>
          </div>

          {/* Repository List */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-primary">▸</span>
              <h2 className="text-sm text-muted-foreground uppercase tracking-widest">
                Repository List
              </h2>
              <div className="flex-1 h-px bg-border ml-2" />
            </div>

            <div className="grid grid-cols-1 gap-4">
              {mockRepositories.map((repo, index) => (
                <RepositoryCard
                  key={repo.id}
                  repository={repo}
                  index={index}
                  className="animate-fade-in-up"
                />
              ))}
            </div>
          </div>

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
