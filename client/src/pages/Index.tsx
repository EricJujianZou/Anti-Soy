import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { TerminalInput } from "@/components/TerminalInput";
import { ProgressTracker, PipelineStep } from "@/components/ProgressTracker";

type ViewState = "landing" | "analyzing";

const mockSteps: PipelineStep[] = [
  { id: "discovery", label: "Repo Discovery", description: "Scanning public repositories", status: "complete" },
  { id: "extraction", label: "Code Extraction", description: "Pulling source files", status: "complete" },
  { id: "static", label: "Static Analysis", description: "Analyzing code patterns", status: "active" },
  { id: "ai", label: "AI Analysis", description: "Evaluating code quality", status: "pending" },
  { id: "scoring", label: "Scoring", description: "Computing skill metrics", status: "pending" },
  { id: "insights", label: "Insight Generation", description: "Building recommendations", status: "pending" },
];

const Index = () => {
  const [viewState, setViewState] = useState<ViewState>("landing");
  const [username, setUsername] = useState("");
  const navigate = useNavigate();

  const handleSubmit = (value: string) => {
    setUsername(value);
    setViewState("analyzing");

    // Simulate analysis completion then navigate to repositories
    setTimeout(() => {
      navigate("/repositories");
    }, 3000);
  };

  const handleReset = () => {
    setViewState("landing");
    setUsername("");
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
            </div>

            <ProgressTracker steps={mockSteps} className="w-full max-w-md" />

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
