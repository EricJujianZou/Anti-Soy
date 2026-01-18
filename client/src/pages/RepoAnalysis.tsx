import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { ScoreDisplay } from "@/components/ScoreDisplay";
import { InsightsList, Insight } from "@/components/InsightsList";
import { RadarChart } from "@/components/RadarChart";
import { LanguagesDisplay } from "@/components/LanguagesDisplay";
import { AsciiPanel } from "@/components/AsciiPanel";
import { ProgressTracker } from "@/components/ProgressTracker";

// Mock repository data - would come from API in real implementation
type MetricSignal = {
  label: string;
  value: string;
  tone: "good" | "warn" | "bad" | "neutral";
};

const mockRepoData: Record<string, {
  name: string;
  description: string;
  language: string;
  languageColor: string;
  stars: number;
  forks: number;
  lastUpdated: string;
  isPrivate: boolean;
  overallScore: number;
  aiDetection: number;
  totalCommits: number;
  contributors: number;
  openIssues: number;
  pullRequests: number;
  radarData: { label: string; value: number }[];
  languages: { name: string; percentage: number }[];
  strengths: Insight[];
  redFlags: Insight[];
  suggestions: Insight[];
  metrics: {
    aiUsage: {
      score: number;
      signals: MetricSignal[];
    };
    productionReadiness: {
      score: number;
      scalability: number;
      errorHandling: number;
      signals: MetricSignal[];
    };
    aiSuggestions: Insight[];
  };
}> = {
  "neural-search-engine": {
    name: "neural-search-engine",
    description: "A semantic search engine powered by transformer embeddings and FAISS for lightning-fast similarity matching across large document corpora.",
    language: "Python",
    languageColor: "#3572A5",
    stars: 847,
    forks: 124,
    lastUpdated: "2 days ago",
    isPrivate: false,
    overallScore: 92,
    aiDetection: 8,
    totalCommits: 487,
    contributors: 12,
    openIssues: 15,
    pullRequests: 3,
    radarData: [
      { label: "Code Quality", value: 88 },
      { label: "Documentation", value: 75 },
      { label: "Testing", value: 82 },
      { label: "Architecture", value: 90 },
      { label: "Security", value: 85 },
      { label: "Performance", value: 94 },
    ],
    languages: [
      { name: "Python", percentage: 72.5 },
      { name: "Cython", percentage: 15.2 },
      { name: "Shell", percentage: 8.3 },
      { name: "Dockerfile", percentage: 4.0 },
    ],
    strengths: [
      { id: "1", type: "strength", text: "Excellent test coverage with 85%+ code coverage" },
      { id: "2", type: "strength", text: "Well-documented API with comprehensive examples" },
      { id: "3", type: "strength", text: "Clean separation of concerns in architecture" },
      { id: "4", type: "strength", text: "Active maintenance with regular updates" },
    ],
    redFlags: [
      { id: "1", type: "red-flag", text: "Some deprecated dependencies need updating" },
      { id: "2", type: "red-flag", text: "Missing type hints in older modules" },
    ],
    suggestions: [
      { id: "1", type: "hint", text: "Consider adding async support for batch operations" },
      { id: "2", type: "hint", text: "Add benchmarking suite for performance regression testing" },
    ],
    metrics: {
      aiUsage: {
        score: 12,
        signals: [
          { label: "AI Comment Markers", value: "0 files", tone: "good" },
          { label: "LLM Commit Signal", value: "9%", tone: "good" },
          { label: "Generated Boilerplate", value: "Low", tone: "good" },
        ],
      },
      productionReadiness: {
        score: 88,
        scalability: 90,
        errorHandling: 84,
        signals: [
          { label: "Async Pipelines", value: "Present", tone: "good" },
          { label: "Retries/Fallbacks", value: "Partial", tone: "warn" },
          { label: "Caching Layer", value: "FAISS + Redis", tone: "good" },
        ],
      },
      aiSuggestions: [
        { id: "1", type: "hint", text: "Add structured logging to async workers for easier incident triage" },
        { id: "2", type: "hint", text: "Introduce retry budgets and circuit breakers on embedding fetches" },
      ],
    },
  },
  "react-terminal-ui": {
    name: "react-terminal-ui",
    description: "A customizable terminal emulator component for React applications with command history, autocomplete, and theming support.",
    language: "TypeScript",
    languageColor: "#3178c6",
    stars: 1243,
    forks: 89,
    lastUpdated: "5 days ago",
    isPrivate: false,
    overallScore: 88,
    aiDetection: 5,
    totalCommits: 324,
    contributors: 8,
    openIssues: 23,
    pullRequests: 5,
    radarData: [
      { label: "Code Quality", value: 92 },
      { label: "Documentation", value: 85 },
      { label: "Testing", value: 78 },
      { label: "Architecture", value: 88 },
      { label: "Security", value: 90 },
      { label: "Performance", value: 82 },
    ],
    languages: [
      { name: "TypeScript", percentage: 68.2 },
      { name: "CSS", percentage: 18.5 },
      { name: "JavaScript", percentage: 10.3 },
      { name: "HTML", percentage: 3.0 },
    ],
    strengths: [
      { id: "1", type: "strength", text: "Fully typed with comprehensive TypeScript definitions" },
      { id: "2", type: "strength", text: "Accessible component with ARIA support" },
      { id: "3", type: "strength", text: "Extensive customization options via props" },
    ],
    redFlags: [
      { id: "1", type: "red-flag", text: "Bundle size could be optimized" },
    ],
    suggestions: [
      { id: "1", type: "hint", text: "Consider tree-shaking for smaller bundle size" },
      { id: "2", type: "hint", text: "Add Storybook for component documentation" },
    ],
    metrics: {
      aiUsage: {
        score: 18,
        signals: [
          { label: "AI Comment Markers", value: "1 file", tone: "warn" },
          { label: "LLM Commit Signal", value: "14%", tone: "neutral" },
          { label: "Generated Boilerplate", value: "Minimal", tone: "good" },
        ],
      },
      productionReadiness: {
        score: 81,
        scalability: 78,
        errorHandling: 86,
        signals: [
          { label: "Bundle Splitting", value: "Partial", tone: "warn" },
          { label: "Error Boundaries", value: "Present", tone: "good" },
          { label: "Telemetry Hooks", value: "Missing", tone: "bad" },
        ],
      },
      aiSuggestions: [
        { id: "1", type: "hint", text: "Add error boundary coverage for all interactive widgets" },
        { id: "2", type: "hint", text: "Ship telemetry hooks for command usage and failure paths" },
      ],
    },
  },
  "cloud-infra-toolkit": {
    name: "cloud-infra-toolkit",
    description: "Infrastructure as Code templates and utilities for deploying scalable microservices on AWS, GCP, and Azure.",
    language: "Go",
    languageColor: "#00ADD8",
    stars: 432,
    forks: 67,
    lastUpdated: "1 week ago",
    isPrivate: false,
    overallScore: 85,
    aiDetection: 3,
    totalCommits: 678,
    contributors: 15,
    openIssues: 8,
    pullRequests: 2,
    radarData: [
      { label: "Code Quality", value: 85 },
      { label: "Documentation", value: 92 },
      { label: "Testing", value: 70 },
      { label: "Architecture", value: 88 },
      { label: "Security", value: 95 },
      { label: "Performance", value: 80 },
    ],
    languages: [
      { name: "Go", percentage: 55.0 },
      { name: "HCL", percentage: 28.5 },
      { name: "Shell", percentage: 12.0 },
      { name: "YAML", percentage: 4.5 },
    ],
    strengths: [
      { id: "1", type: "strength", text: "Comprehensive multi-cloud support" },
      { id: "2", type: "strength", text: "Security-first design with IAM best practices" },
      { id: "3", type: "strength", text: "Excellent documentation with real-world examples" },
    ],
    redFlags: [
      { id: "1", type: "red-flag", text: "Integration tests need expansion" },
      { id: "2", type: "red-flag", text: "Some Terraform modules lack versioning" },
    ],
    suggestions: [
      { id: "1", type: "hint", text: "Add cost estimation features" },
      { id: "2", type: "hint", text: "Consider adding drift detection capabilities" },
    ],
    metrics: {
      aiUsage: {
        score: 6,
        signals: [
          { label: "AI Comment Markers", value: "0 files", tone: "good" },
          { label: "LLM Commit Signal", value: "4%", tone: "good" },
          { label: "Generated Boilerplate", value: "Low", tone: "good" },
        ],
      },
      productionReadiness: {
        score: 86,
        scalability: 92,
        errorHandling: 79,
        signals: [
          { label: "Multi-Region Design", value: "Strong", tone: "good" },
          { label: "Retry Strategy", value: "Basic", tone: "warn" },
          { label: "Secrets Hygiene", value: "Good", tone: "good" },
        ],
      },
      aiSuggestions: [
        { id: "1", type: "hint", text: "Add exponential backoff templates for all cloud providers" },
        { id: "2", type: "hint", text: "Document failure-mode playbooks per service module" },
      ],
    },
  },
  "ml-pipeline-orchestrator": {
    name: "ml-pipeline-orchestrator",
    description: "End-to-end ML pipeline management with experiment tracking, model versioning, and automated deployment workflows.",
    language: "Python",
    languageColor: "#3572A5",
    stars: 289,
    forks: 41,
    lastUpdated: "2 weeks ago",
    isPrivate: true,
    overallScore: 79,
    aiDetection: 15,
    totalCommits: 234,
    contributors: 5,
    openIssues: 12,
    pullRequests: 4,
    radarData: [
      { label: "Code Quality", value: 75 },
      { label: "Documentation", value: 68 },
      { label: "Testing", value: 72 },
      { label: "Architecture", value: 85 },
      { label: "Security", value: 78 },
      { label: "Performance", value: 80 },
    ],
    languages: [
      { name: "Python", percentage: 82.0 },
      { name: "YAML", percentage: 10.5 },
      { name: "Shell", percentage: 5.0 },
      { name: "Dockerfile", percentage: 2.5 },
    ],
    strengths: [
      { id: "1", type: "strength", text: "Good MLOps practices with model versioning" },
      { id: "2", type: "strength", text: "Flexible pipeline configuration" },
    ],
    redFlags: [
      { id: "1", type: "red-flag", text: "Higher AI-generated code detection" },
      { id: "2", type: "red-flag", text: "Documentation could be more comprehensive" },
      { id: "3", type: "red-flag", text: "Limited error handling in some modules" },
    ],
    suggestions: [
      { id: "1", type: "hint", text: "Add more detailed logging throughout pipelines" },
      { id: "2", type: "hint", text: "Consider implementing circuit breakers" },
      { id: "3", type: "hint", text: "Review and refactor AI-generated sections" },
    ],
    metrics: {
      aiUsage: {
        score: 32,
        signals: [
          { label: "AI Comment Markers", value: "4 files", tone: "warn" },
          { label: "LLM Commit Signal", value: "28%", tone: "warn" },
          { label: "Generated Boilerplate", value: "Moderate", tone: "neutral" },
        ],
      },
      productionReadiness: {
        score: 72,
        scalability: 74,
        errorHandling: 68,
        signals: [
          { label: "Queue Backpressure", value: "Partial", tone: "warn" },
          { label: "Retry/Fallbacks", value: "Minimal", tone: "bad" },
          { label: "Model Registry", value: "Present", tone: "good" },
        ],
      },
      aiSuggestions: [
        { id: "1", type: "hint", text: "Define strict retry policies for job orchestration failures" },
        { id: "2", type: "hint", text: "Introduce request tracing between pipeline stages" },
      ],
    },
  },
  "rust-crypto-lib": {
    name: "rust-crypto-lib",
    description: "High-performance cryptographic primitives implemented in Rust with zero-copy operations and constant-time guarantees.",
    language: "Rust",
    languageColor: "#dea584",
    stars: 567,
    forks: 78,
    lastUpdated: "3 weeks ago",
    isPrivate: false,
    overallScore: 95,
    aiDetection: 2,
    totalCommits: 892,
    contributors: 18,
    openIssues: 5,
    pullRequests: 1,
    radarData: [
      { label: "Code Quality", value: 96 },
      { label: "Documentation", value: 88 },
      { label: "Testing", value: 94 },
      { label: "Architecture", value: 92 },
      { label: "Security", value: 98 },
      { label: "Performance", value: 95 },
    ],
    languages: [
      { name: "Rust", percentage: 92.5 },
      { name: "Assembly", percentage: 5.0 },
      { name: "C", percentage: 2.0 },
      { name: "Shell", percentage: 0.5 },
    ],
    strengths: [
      { id: "1", type: "strength", text: "Memory-safe implementation with zero unsafe blocks" },
      { id: "2", type: "strength", text: "Comprehensive fuzzing and property-based testing" },
      { id: "3", type: "strength", text: "Constant-time operations prevent timing attacks" },
      { id: "4", type: "strength", text: "Extensively audited by security researchers" },
    ],
    redFlags: [],
    suggestions: [
      { id: "1", type: "hint", text: "Consider WASM compilation for browser support" },
    ],
    metrics: {
      aiUsage: {
        score: 4,
        signals: [
          { label: "AI Comment Markers", value: "0 files", tone: "good" },
          { label: "LLM Commit Signal", value: "2%", tone: "good" },
          { label: "Generated Boilerplate", value: "None", tone: "good" },
        ],
      },
      productionReadiness: {
        score: 94,
        scalability: 92,
        errorHandling: 96,
        signals: [
          { label: "Constant-Time APIs", value: "Verified", tone: "good" },
          { label: "Fail-Safe Defaults", value: "Strong", tone: "good" },
          { label: "Fuzzing Coverage", value: "Extensive", tone: "good" },
        ],
      },
      aiSuggestions: [
        { id: "1", type: "hint", text: "Add performance regression guards for new cipher suites" },
        { id: "2", type: "hint", text: "Expose structured error enums for integration callers" },
      ],
    },
  },
};

// Default data for unknown repos
const defaultRepoData = {
  name: "Unknown Repository",
  description: "Repository not found in the system.",
  language: "Unknown",
  languageColor: "#808080",
  stars: 0,
  forks: 0,
  lastUpdated: "Unknown",
  isPrivate: false,
  overallScore: 0,
  aiDetection: 0,
  totalCommits: 0,
  contributors: 0,
  openIssues: 0,
  pullRequests: 0,
  radarData: [
    { label: "Code Quality", value: 0 },
    { label: "Documentation", value: 0 },
    { label: "Testing", value: 0 },
    { label: "Architecture", value: 0 },
    { label: "Security", value: 0 },
    { label: "Performance", value: 0 },
  ],
  languages: [],
  strengths: [],
  redFlags: [],
  suggestions: [],
  metrics: {
    aiUsage: {
      score: 0,
      signals: [],
    },
    productionReadiness: {
      score: 0,
      scalability: 0,
      errorHandling: 0,
      signals: [],
    },
    aiSuggestions: [],
  },
};

const RepoAnalysis = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const repo = repoId ? mockRepoData[repoId] || defaultRepoData : defaultRepoData;
  const [isAnalyzing, setIsAnalyzing] = useState(true);
  const toneClasses: Record<MetricSignal["tone"], string> = {
    good: "text-primary",
    warn: "text-primary/80",
    bad: "text-foreground",
    neutral: "text-muted-foreground",
  };

  useEffect(() => {
    setIsAnalyzing(true);
    const timer = setTimeout(() => {
      setIsAnalyzing(false);
    }, 5000);

    return () => clearTimeout(timer);
  }, [repoId]);

  return (
    <GridBackground>
      <Header />

      <main className="container mx-auto px-4 py-12">
        {isAnalyzing ? (
          <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-foreground mb-2">
                Analyzing <span className="text-primary">{repo.name}</span>
              </h2>
              <p className="text-sm text-muted-foreground">
                Running deeper metrics and signal checks
              </p>
            </div>

            <ProgressTracker className="w-full max-w-md" />

            <Link
              to="/repositories"
              className="mt-8 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              ← Back to repositories
            </Link>
          </div>
        ) : (
          <div className="animate-fade-in-up">
            {/* Page Header */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <Link
                    to="/repositories"
                    className="text-muted-foreground hover:text-foreground transition-colors text-sm"
                  >
                    ← Repositories
                  </Link>
                  <span className="text-muted-foreground">/</span>
                  <h1 className="text-2xl font-bold text-foreground">
                    <span className="text-primary text-glow">{repo.name}</span>
                  </h1>
                  {repo.isPrivate && (
                    <span className="text-[10px] px-1.5 py-0.5 border border-muted text-muted-foreground uppercase tracking-wider">
                      Private
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground max-w-2xl">
                  {repo.description}
                </p>
              </div>
            </div>

            {/* Quick Stats Bar */}
            <div className="flex items-center gap-6 mb-6 text-sm">
            <div className="flex items-center gap-1.5">
              <span className="glyph-spinner text-sm text-primary leading-none" aria-hidden="true" />
              <span className="text-foreground">{repo.language}</span>
            </div>
              <div className="flex items-center gap-1 text-muted-foreground">
                <span>★</span>
                <span>{repo.stars.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground">
                <span>⑂</span>
                <span>{repo.forks.toLocaleString()}</span>
              </div>
              <div className="text-muted-foreground">
                Updated {repo.lastUpdated}
              </div>
            </div>

            {/* Score Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <ScoreDisplay
                label="Repository Score"
                value={repo.overallScore}
              />
              <ScoreDisplay
                label="AI Detection"
                value={repo.aiDetection}
                suffix="%"
              />
              <ScoreDisplay
                label="Total Commits"
                value={repo.totalCommits}
                maxValue={1000}
              />
            </div>

            {/* Languages */}
            {repo.languages.length > 0 && (
              <LanguagesDisplay languages={repo.languages} className="mb-6" />
            )}

            {/* Metrics */}
            <div className="space-y-4 mb-6">
              <div className="flex items-center gap-2">
                <span className="text-primary">▸</span>
                <h2 className="text-xs uppercase tracking-widest text-muted-foreground">
                  Metric Breakdown
                </h2>
                <div className="flex-1 h-px bg-border ml-2" />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <AsciiPanel title="AI Usage" variant="highlight">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs uppercase tracking-widest text-muted-foreground">
                        AI Footprint
                      </div>
                      <div className="text-3xl font-bold text-primary tabular-nums">
                        {repo.metrics.aiUsage.score}%
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground text-right">
                      Higher means more AI
                      <br />
                      usage detected
                    </div>
                  </div>
                  <div className="mt-4 space-y-2 text-sm">
                    {repo.metrics.aiUsage.signals.map((signal) => (
                      <div key={signal.label} className="flex justify-between">
                        <span className="text-muted-foreground">{signal.label}</span>
                        <span className={toneClasses[signal.tone]}>{signal.value}</span>
                      </div>
                    ))}
                  </div>
                </AsciiPanel>

                <AsciiPanel title="Production Readiness">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs uppercase tracking-widest text-muted-foreground">
                        Overall Score
                      </div>
                      <div className="text-3xl font-bold text-primary tabular-nums">
                        {repo.metrics.productionReadiness.score}
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground text-right">
                      Scalability +
                      <br />
                      Error Handling
                    </div>
                  </div>

                  <div className="mt-4 space-y-3 text-sm">
                    <div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Scalability</span>
                        <span className="text-foreground tabular-nums">
                          {repo.metrics.productionReadiness.scalability}/100
                        </span>
                      </div>
                      <div className="mt-1 h-1 bg-muted rounded-sm overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-500 ease-out"
                          style={{ width: `${repo.metrics.productionReadiness.scalability}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Error Handling</span>
                        <span className="text-foreground tabular-nums">
                          {repo.metrics.productionReadiness.errorHandling}/100
                        </span>
                      </div>
                      <div className="mt-1 h-1 bg-muted rounded-sm overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-500 ease-out"
                          style={{ width: `${repo.metrics.productionReadiness.errorHandling}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 space-y-2 text-sm">
                    {repo.metrics.productionReadiness.signals.map((signal) => (
                      <div key={signal.label} className="flex justify-between">
                        <span className="text-muted-foreground">{signal.label}</span>
                        <span className={toneClasses[signal.tone]}>{signal.value}</span>
                      </div>
                    ))}
                  </div>
                </AsciiPanel>
              </div>

              {repo.metrics.aiSuggestions.length > 0 && (
                <InsightsList
                  title="AI Suggestions"
                  insights={repo.metrics.aiSuggestions}
                />
              )}
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <InsightsList
                    title="Strengths"
                    insights={repo.strengths}
                  />
                  <InsightsList
                    title="Red Flags"
                    insights={repo.redFlags}
                  />
                </div>

                <InsightsList
                  title="Suggestions"
                  insights={repo.suggestions}
                />
              </div>

              <div>
                <RadarChart data={repo.radarData} />

                <AsciiPanel title="Repository Stats" className="mt-4">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Contributors</span>
                      <span className="text-foreground font-medium">{repo.contributors}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Open Issues</span>
                      <span className="text-foreground font-medium">{repo.openIssues}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Pull Requests</span>
                      <span className="text-foreground font-medium">{repo.pullRequests}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total Commits</span>
                      <span className="text-foreground font-medium">{repo.totalCommits.toLocaleString()}</span>
                    </div>
                  </div>
                </AsciiPanel>

                <AsciiPanel title="Analysis Info" className="mt-4" variant="muted">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Analyzed</span>
                      <span className="text-foreground font-medium">{new Date().toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Analysis Version</span>
                      <span className="text-foreground font-medium">v2.1.0</span>
                    </div>
                  </div>
                </AsciiPanel>
              </div>
            </div>
          </div>
        )}
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

export default RepoAnalysis;
