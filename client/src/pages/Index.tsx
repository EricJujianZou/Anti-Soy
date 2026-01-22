import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { TerminalInput } from "@/components/TerminalInput";
import { ProgressTracker, PipelineStep } from "@/components/ProgressTracker";
import { useCreateUserMetadata } from "@/hooks/useApi";

type ViewState = "landing" | "analyzing";

const Index = () => {
  const [viewState, setViewState] = useState<ViewState>("landing");
  const [username, setUsername] = useState("");
  const [steps, setSteps] = useState<PipelineStep[]>([
    { id: "discovery", label: "Repo Discovery", description: "Scanning public repositories", status: "pending" },
    { id: "extraction", label: "Code Extraction", description: "Pulling source files", status: "pending" },
    { id: "static", label: "Static Analysis", description: "Analyzing code patterns", status: "pending" },
    { id: "ai", label: "AI Analysis", description: "Evaluating code quality", status: "pending" },
    { id: "scoring", label: "Scoring", description: "Computing skill metrics", status: "pending" },
    { id: "insights", label: "Insight Generation", description: "Building recommendations", status: "pending" },
  ]);
  const navigate = useNavigate();
  const mutation = useCreateUserMetadata();

  // Animate steps while loading
  useEffect(() => {
    if (mutation.isPending) {
      const stepOrder = ["discovery", "extraction", "static", "ai", "scoring", "insights"];
      let currentIndex = 0;

      const interval = setInterval(() => {
        setSteps((prev) =>
          prev.map((step, idx) => ({
            ...step,
            status: idx < currentIndex ? "complete" : idx === currentIndex ? "active" : "pending",
          }))
        );
        currentIndex++;
        if (currentIndex > stepOrder.length) {
          clearInterval(interval);
        }
      }, 500);

      return () => clearInterval(interval);
    }
  }, [mutation.isPending]);

  // Navigate on success
  useEffect(() => {
    if (mutation.isSuccess) {
      // Mark all steps complete
      setSteps((prev) => prev.map((step) => ({ ...step, status: "complete" })));
      // Navigate to repositories with username
      setTimeout(() => {
        navigate(`/repositories?user=${encodeURIComponent(mutation.data.username)}`);
      }, 500);
    }
  }, [mutation.isSuccess, mutation.data, navigate]);

  const handleSubmit = (value: string) => {
    setUsername(value);
    setViewState("analyzing");
    // Reset steps
    setSteps((prev) => prev.map((step) => ({ ...step, status: "pending" })));
    // Trigger API call
    mutation.mutate(value);
  };

  const handleReset = () => {
    setViewState("landing");
    setUsername("");
    mutation.reset();
    setSteps((prev) => prev.map((step) => ({ ...step, status: "pending" })));
  };

  return (
    <GridBackground>
      <Header />

      <main className="container mx-auto px-4 py-12">
        {viewState === "landing" && (
          <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
            <div className="text-center mb-12 max-w-xl">
              <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                Analyze a GitHub profile
                <br />
                <span className="text-primary text-glow">in ~3 minutes</span>
              </h1>
            </div>

            <TerminalInput onSubmit={handleSubmit} />
          </div>
        )}

        {viewState === "analyzing" && (
          <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-foreground mb-2">
                Analyzing <span className="text-primary">@{username}</span>
              </h2>
              {mutation.isError && (
                <p className="text-sm text-red-500 mt-2">
                  Error: {mutation.error?.message || "Failed to fetch user data"}
                </p>
              )}
            </div>

            <ProgressTracker steps={steps} className="w-full max-w-md" />

            <button
              onClick={handleReset}
              className="mt-8 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              ← Cancel
            </button>
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

export default Index;
