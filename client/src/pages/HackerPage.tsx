import { useNavigate } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { TerminalInput } from "@/components/TerminalInput";
import { type PriorityKey } from "@/services/api";

const HackerPage = () => {
  const navigate = useNavigate();

  const handleSubmit = (repoUrl: string, _priorities: PriorityKey[]) => {
    if (repoUrl.includes("github.com")) {
      if (typeof gtag !== "undefined") {
        gtag("event", "analysis_started", {
          event_category: "engagement",
          portal: "hacker",
          repo_url: repoUrl,
        });
      }
      const params = new URLSearchParams({
        link: repoUrl,
        mode: "hacker",
      });
      navigate(`/repo/new?${params.toString()}`);
    } else {
      alert("Please enter a valid GitHub repository URL.");
    }
  };

  return (
    <GridBackground>
      <div className="flex flex-col min-h-screen">
        <Header />

        <main className="container mx-auto px-4 py-12">
          <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
            <div className="text-center mb-12 max-w-2xl">
              <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                Find the good random
                <br />
                <span style={{ color: "hsl(var(--hacker))" }}>for your team.</span>
              </h1>
              <p className="text-muted-foreground">
                Paste a potential teammate's GitHub. We'll tell you if they can actually build.
              </p>
            </div>

            <h2
              className="text-xl md:text-2xl font-bold mb-6 uppercase tracking-widest"
              style={{ color: "hsl(var(--hacker))" }}
            >
              Analyze Teammate
            </h2>

            {/* Scope the cyan theme by overriding --primary at CSS variable level */}
            <div
              className="w-full flex justify-center"
              style={{
                "--primary": "var(--hacker)",
                "--primary-foreground": "var(--hacker-foreground)",
                "--ring": "var(--hacker)",
              } as React.CSSProperties}
            >
              <TerminalInput
                onSubmit={handleSubmit}
                placeholder="https://github.com/teammate/repository"
                hidePriorities
                submitLabel="[ analyze teammate ]"
                examples={[
                  { label: "To-Do List", url: "https://github.com/chaosium43/METROHACKS22" },
                  { label: "GPT Wrapper", url: "https://github.com/EricJujianZou/PromptAssist" },
                  { label: "Algorithm", url: "https://github.com/Skullheadx/The-Traveling-Salesman-Problem" },
                ]}
              />
            </div>
          </div>
        </main>

        <footer className="border-t border-border py-6">
          <p className="text-center text-xs text-muted-foreground uppercase tracking-widest font-mono">
            Built to filter signal from noise.
          </p>
        </footer>
      </div>
    </GridBackground>
  );
};

export default HackerPage;
