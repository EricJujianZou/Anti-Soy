import { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { ProgressTracker, PipelineStep } from "@/components/ProgressTracker";
import { useAnalyzeAndEvaluateRepo } from "@/hooks/useApi";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Terminal } from "lucide-react";

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
    { id: "clone", label: "Cloning Repository", description: "Getting the code", status: "pending" },
    { id: "analyze", label: "Static Analysis", description: "Running code & pattern checks", status: "pending" },
    { id: "evaluate", label: "LLM Evaluation", description: "Assessing business value", status: "pending" },
    { id: "complete", label: "Complete", description: "Analysis ready", status: "pending" },
  ]);

  const mutation = useAnalyzeAndEvaluateRepo();
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
        if (currentIndex > steps.length) clearInterval(interval);
      }, 800);
      return () => clearInterval(interval);
    }
  }, [mutation.isPending, steps.length]);

  // Mark all steps complete on success
  useEffect(() => {
    if (mutation.isSuccess) {
      setSteps((prev) => prev.map((step) => ({ ...step, status: "complete" })));
    }
  }, [mutation.isSuccess]);

  const repoName = repoLink ? getRepoName(repoLink) : repoId || "Unknown";
  const isLoading = mutation.isPending;
  const analysisData = mutation.data ? mutation.data[0] : null;
  const evaluationData = mutation.data ? mutation.data[1] : null;

  // If no repo link provided, show error
  if (!repoLink) {
    return (
      <GridBackground>
        <Header />
        <main className="container mx-auto flex min-h-[70vh] items-center justify-center px-4 py-12">
          <div className="text-center">
            <h2 className="text-2xl font-bold">No repository specified</h2>
            <p className="text-muted-foreground mt-2 mb-4">
              Please go back and select a repository to analyze.
            </p>
            <Link to="/" className="text-primary hover:underline">
              ← Back to home
            </Link>
          </div>
        </main>
      </GridBackground>
    );
  }

  const renderContent = () => {
    if (isLoading || !evaluationData || !analysisData) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-foreground mb-2">
              Analyzing <span className="text-primary">{repoName}</span>
            </h2>
            <p className="text-sm text-muted-foreground">
              Running deeper metrics and signal checks...
            </p>
            {mutation.isError && (
              <p className="text-sm text-red-500 mt-2">
                Error: {mutation.error?.message || "Failed to analyze repository"}
              </p>
            )}
          </div>
          <ProgressTracker steps={steps} className="w-full max-w-md" />
        </div>
      );
    }

    // STEP 1: Render At-a-Glance Signal (Reject Flag or Standout Headline)
    return (
      <div className="animate-fade-in-up space-y-8">
        {evaluationData.is_rejected ? (
          <Alert variant="destructive" className="border-2">
            <Terminal className="h-4 w-4" />
            <AlertTitle className="text-xl font-bold">REJECT</AlertTitle>
            <AlertDescription className="text-base">
              {evaluationData.rejection_reason || "A critical issue was found that warrants immediate rejection."}
            </AlertDescription>
          </Alert>
        ) : (
          <div className="p-6 rounded-lg bg-card border">
            <h2 className="text-xs uppercase tracking-widest text-muted-foreground">
              Standout Feature
            </h2>
            <p className="text-2xl font-bold text-primary mt-1">
              {evaluationData.standout_features.join(' - ') || "A solid project with standard practices."}
            </p>
          </div>
        )}
        
        {/* Placeholder for Step 2: Business Value Validator */}
        <div className="p-4 rounded-lg bg-card border-dashed border-2 text-center text-muted-foreground">
          <p>Step 2: Business Value Validator will go here.</p>
        </div>

        {/* Placeholder for Step 3: Critical Issues */}
        <div className="p-4 rounded-lg bg-card border-dashed border-2 text-center text-muted-foreground">
          <p>Step 3: Critical Issues will go here.</p>
        </div>
        
        {/* ... other placeholders ... */}
      </div>
    );
  };

  return (
    <GridBackground>
      <Header />
      <main className="container mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors text-sm">
                ← Home
              </Link>
              <span className="text-muted-foreground">/</span>
              <h1 className="text-2xl font-bold text-foreground">
                <span className="text-primary text-glow">{repoName}</span>
              </h1>
            </div>
            <a href={repoLink} target="_blank" rel="noopener noreferrer" className="text-sm text-muted-foreground hover:text-primary transition-colors max-w-2xl break-all">
              {repoLink}
            </a>
          </div>
        </div>
        {renderContent()}
      </main>
    </GridBackground>
  );
};

export default RepoAnalysis;
