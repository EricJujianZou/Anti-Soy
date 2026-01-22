import { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { ScoreDisplay } from "@/components/ScoreDisplay";
import { InsightsList } from "@/components/InsightsList";
import { RadarChart } from "@/components/RadarChart";
import { AsciiPanel } from "@/components/AsciiPanel";
import { ProgressTracker, PipelineStep } from "@/components/ProgressTracker";
import { useAnalyzeRepo } from "@/hooks/useApi";
import { RepoAnalysis as RepoAnalysisData } from "@/services/api";
import {
  computeOverallScore,
  computeRadarData,
  computeAIUsageLevel,
  generateStrengths,
  generateRedFlags,
  generateSuggestions,
  generateProductionSignals,
  generateAIUsageSignals,
  computeProductionReadinessScore,
  computeScalabilityScore,
  generateAISuggestions,
} from "@/lib/scoring";

type MetricSignal = {
  label: string;
  value: string;
  tone: "good" | "warn" | "bad" | "neutral";
};

// Helper to extract repo name from github link
function getRepoName(githubLink: string): string {
  const parts = githubLink.replace(/\/$/, "").split("/");
  return parts[parts.length - 1] || "Unknown";
}

const RepoAnalysis = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const [searchParams] = useSearchParams();
  const repoLink = searchParams.get("link");

  const [steps, setSteps] = useState<PipelineStep[]>([
    { id: "fetch", label: "Fetching Repository", description: "Cloning and indexing files", status: "pending" },
    { id: "static", label: "Static Analysis", description: "Analyzing code patterns", status: "pending" },
    { id: "metrics", label: "Computing Metrics", description: "Evaluating quality signals", status: "pending" },
    { id: "ai", label: "AI Analysis", description: "Deep code inspection", status: "pending" },
    { id: "scoring", label: "Scoring", description: "Calculating final scores", status: "pending" },
    { id: "complete", label: "Complete", description: "Analysis ready", status: "pending" },
  ]);

  const mutation = useAnalyzeRepo();
  const [hasStarted, setHasStarted] = useState(false);

  // Start analysis when component mounts with a valid repo link
  useEffect(() => {
    if (repoLink && !hasStarted) {
      setHasStarted(true);
      mutation.mutate(repoLink);
    }
  }, [repoLink, hasStarted, mutation]);

  // Animate steps while loading
  useEffect(() => {
    if (mutation.isPending) {
      let currentIndex = 0;

      const interval = setInterval(() => {
        setSteps((prev) =>
          prev.map((step, idx) => ({
            ...step,
            status: idx < currentIndex ? "complete" : idx === currentIndex ? "active" : "pending",
          }))
        );
        currentIndex++;
        if (currentIndex > steps.length) {
          clearInterval(interval);
        }
      }, 800);

      return () => clearInterval(interval);
    }
  }, [mutation.isPending]);

  // Mark all steps complete on success
  useEffect(() => {
    if (mutation.isSuccess) {
      setSteps((prev) => prev.map((step) => ({ ...step, status: "complete" })));
    }
  }, [mutation.isSuccess]);

  const toneClasses: Record<MetricSignal["tone"], string> = {
    good: "text-primary",
    warn: "text-primary/80",
    bad: "text-foreground",
    neutral: "text-muted-foreground",
  };

  const analysis = mutation.data;
  const isLoading = mutation.isPending;

  // Compute derived data from analysis
  const repoName = repoLink ? getRepoName(repoLink) : repoId || "Unknown";
  const overallScore = analysis ? computeOverallScore(analysis) : 0;
  const radarData = analysis ? computeRadarData(analysis) : [];
  const aiUsage = analysis ? computeAIUsageLevel(analysis) : null;
  const strengths = analysis ? generateStrengths(analysis) : [];
  const redFlags = analysis ? generateRedFlags(analysis) : [];
  const suggestions = analysis ? generateSuggestions(analysis) : [];
  const productionSignals = analysis ? generateProductionSignals(analysis) : [];
  const aiUsageSignals = analysis ? generateAIUsageSignals(analysis) : [];
  const productionReadinessScore = analysis ? computeProductionReadinessScore(analysis) : 0;
  const scalabilityScore = analysis ? computeScalabilityScore(analysis) : 0;
  const errorHandlingScore = analysis ? analysis.error_handling.score : 0;
  const aiSuggestions = analysis ? generateAISuggestions(analysis) : [];

  // If no repo link provided, show error
  if (!repoLink) {
    return (
      <GridBackground>
        <Header />
        <main className="container mx-auto px-4 py-12">
          <div className="flex flex-col items-center justify-center min-h-[70vh]">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-foreground mb-4">
                No repository specified
              </h2>
              <p className="text-muted-foreground mb-4">
                Please select a repository from the repositories page.
              </p>
              <Link to="/repositories" className="text-primary hover:underline">
                ← Back to repositories
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
        {isLoading || !analysis ? (
          <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-foreground mb-2">
                Analyzing <span className="text-primary">{repoName}</span>
              </h2>
              <p className="text-sm text-muted-foreground">
                Running deeper metrics and signal checks
              </p>
              {mutation.isError && (
                <p className="text-sm text-red-500 mt-2">
                  Error: {mutation.error?.message || "Failed to analyze repository"}
                </p>
              )}
            </div>

            <ProgressTracker steps={steps} className="w-full max-w-md" />

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
                    <span className="text-primary text-glow">{repoName}</span>
                  </h1>
                </div>
                <p className="text-sm text-muted-foreground max-w-2xl">
                  {repoLink}
                </p>
              </div>
            </div>

            {/* Quick Stats Bar */}
            <div className="flex items-center gap-6 mb-6 text-sm">
              <div className="flex items-center gap-1.5">
                <span className="glyph-spinner text-sm text-primary leading-none" aria-hidden="true" />
                <span className="text-foreground">Repository</span>
              </div>
              <div className="text-muted-foreground">
                Status: {analysis.status}
              </div>
            </div>

            {/* Score Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <ScoreDisplay
                label="Repository Score"
                value={overallScore}
              />
              <ScoreDisplay
                label="AI Footprint"
                value={aiUsage?.level ?? "Low"}
              />
              <ScoreDisplay
                label="Production Ready"
                value={productionReadinessScore}
                maxValue={100}
              />
            </div>

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
                        AI Usage
                      </div>
                      <div className="text-3xl font-bold text-primary tabular-nums">
                        {aiUsage?.level ?? "Low"}
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground text-right">
                      Comment and commit
                      <br />
                      patterns combined
                    </div>
                  </div>
                  <div className="mt-4 space-y-2 text-sm">
                    {aiUsageSignals.map((signal) => (
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
                        {productionReadinessScore}
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
                          {scalabilityScore}/100
                        </span>
                      </div>
                      <div className="mt-1 h-1 bg-muted rounded-sm overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-500 ease-out"
                          style={{ width: `${scalabilityScore}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Error Handling</span>
                        <span className="text-foreground tabular-nums">
                          {errorHandlingScore}/100
                        </span>
                      </div>
                      <div className="mt-1 h-1 bg-muted rounded-sm overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-500 ease-out"
                          style={{ width: `${errorHandlingScore}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 space-y-2 text-sm">
                    {productionSignals.map((signal) => (
                      <div key={signal.label} className="flex justify-between">
                        <span className="text-muted-foreground">{signal.label}</span>
                        <span className={toneClasses[signal.tone]}>{signal.value}</span>
                      </div>
                    ))}
                  </div>
                </AsciiPanel>
              </div>

              {aiSuggestions.length > 0 && (
                <InsightsList
                  title="AI Suggestions"
                  insights={aiSuggestions}
                />
              )}
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <InsightsList
                    title="Strengths"
                    insights={strengths}
                  />
                  <InsightsList
                    title="Red Flags"
                    insights={redFlags}
                  />
                </div>

                <InsightsList
                  title="Suggestions"
                  insights={suggestions}
                />
              </div>

              <div>
                <RadarChart data={radarData} />

                <AsciiPanel title="Detailed Metrics" className="mt-4">
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Files Organized</span>
                      <span className="text-foreground font-medium">{analysis.files_organized.score}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Test Suites</span>
                      <span className="text-foreground font-medium">{analysis.test_suites.score}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">README Quality</span>
                      <span className="text-foreground font-medium">{analysis.readme.score}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">API Keys Security</span>
                      <span className="text-foreground font-medium">{analysis.api_keys.score}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Error Handling</span>
                      <span className="text-foreground font-medium">{analysis.error_handling.score}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Commit Density</span>
                      <span className="text-foreground font-medium">{analysis.commit_density.score}/100</span>
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
                      <span className="text-muted-foreground">Repo ID</span>
                      <span className="text-foreground font-medium">{analysis.repo_id}</span>
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
