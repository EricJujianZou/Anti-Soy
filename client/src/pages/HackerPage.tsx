import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { cn } from "@/utils/utils";

const DUO_EXAMPLES = [
  {
    label: "Frontend + Backend",
    urlA: "https://github.com/EricJujianZou/PromptAssist",
    urlB: "https://github.com/Skullheadx/The-Traveling-Salesman-Problem",
  },
  {
    label: "Two Vibe Coders",
    urlA: "https://github.com/IshaanKalra2103/shannon",
    urlB: "https://github.com/EricJujianZou/PromptAssist",
  },
];

const isValidGithubInput = (url: string) => {
  const trimmed = url.trim();
  if (!trimmed) return false;
  // Full GitHub URL
  if (trimmed.includes("github.com")) return true;
  // Plain GitHub username (no slashes, alphanumeric + hyphens)
  if (!trimmed.includes("/") && /^[a-zA-Z0-9][a-zA-Z0-9-]*$/.test(trimmed)) return true;
  return false;
};

const HackerPage = () => {
  const navigate = useNavigate();
  const [urlA, setUrlA] = useState("");
  const [urlB, setUrlB] = useState("");
  const [focusedInput, setFocusedInput] = useState<"a" | "b" | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const hasA = isValidGithubInput(urlA);
    const hasB = isValidGithubInput(urlB);

    if (hasA && hasB) {
      // Duo scan
      if (typeof gtag !== "undefined") {
        gtag("event", "duo_scan_started", {
          event_category: "engagement",
          portal: "hacker",
        });
      }
      const params = new URLSearchParams({
        linkA: urlA.trim(),
        linkB: urlB.trim(),
      });
      navigate(`/duo?${params.toString()}`);
    } else if (hasA) {
      // Single scan — person A
      const params = new URLSearchParams({ link: urlA.trim(), mode: "hacker" });
      navigate(`/repo/new?${params.toString()}`);
    } else if (hasB) {
      // Single scan — person B
      const params = new URLSearchParams({ link: urlB.trim(), mode: "hacker" });
      navigate(`/repo/new?${params.toString()}`);
    }
  };

  const handleExample = (exUrlA: string, exUrlB: string) => {
    setUrlA(exUrlA);
    setUrlB(exUrlB);
  };

  const hasAnyInput = urlA.trim() !== "" || urlB.trim() !== "";
  const hasBothValid = isValidGithubInput(urlA) && isValidGithubInput(urlB);
  const hasSingleValid =
    !hasBothValid && (isValidGithubInput(urlA) || isValidGithubInput(urlB));

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
                <span style={{ color: "hsl(var(--hacker))" }}>
                  for your team.
                </span>
              </h1>
              <p className="text-muted-foreground">
                Paste two GitHub repos to compare teammates. Or just one for a
                solo scan.
              </p>
            </div>

            <h2
              className="text-xl md:text-2xl font-bold mb-6 uppercase tracking-widest"
              style={{ color: "hsl(var(--hacker))" }}
            >
              Match Analysis
            </h2>

            {/* Cyan theme override */}
            <form
              onSubmit={handleSubmit}
              className="w-full max-w-3xl"
              style={
                {
                  "--primary": "var(--hacker)",
                  "--primary-foreground": "var(--hacker-foreground)",
                  "--ring": "var(--hacker)",
                } as React.CSSProperties
              }
            >
              {/* Dual inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Person A */}
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
                    Person A
                  </label>
                  <div
                    className={cn(
                      "relative border bg-card/80 backdrop-blur-sm transition-all duration-300",
                      focusedInput === "a"
                        ? "border-primary glow-amber"
                        : "border-border"
                    )}
                  >
                    <span className="absolute -top-px -left-px text-primary text-sm">
                      ┌
                    </span>
                    <span className="absolute -top-px -right-px text-primary text-sm">
                      ┐
                    </span>
                    <span className="absolute -bottom-px -left-px text-primary text-sm">
                      └
                    </span>
                    <span className="absolute -bottom-px -right-px text-primary text-sm">
                      ┘
                    </span>
                    <div className="flex items-center gap-2 p-3">
                      <span className="text-primary font-medium">&gt;</span>
                      <input
                        type="text"
                        value={urlA}
                        onChange={(e) => setUrlA(e.target.value)}
                        onFocus={() => setFocusedInput("a")}
                        onBlur={() => setFocusedInput(null)}
                        placeholder="github.com/teammate-a/repo or username"
                        className="flex-1 bg-transparent border-none outline-none text-foreground placeholder:text-muted-foreground/50 font-mono text-sm"
                      />
                      {focusedInput === "a" && (
                        <span className="w-2 h-4 bg-primary cursor-blink" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Person B */}
                <div>
                  <label className="block text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
                    Person B
                  </label>
                  <div
                    className={cn(
                      "relative border bg-card/80 backdrop-blur-sm transition-all duration-300",
                      focusedInput === "b"
                        ? "border-primary glow-amber"
                        : "border-border"
                    )}
                  >
                    <span className="absolute -top-px -left-px text-primary text-sm">
                      ┌
                    </span>
                    <span className="absolute -top-px -right-px text-primary text-sm">
                      ┐
                    </span>
                    <span className="absolute -bottom-px -left-px text-primary text-sm">
                      └
                    </span>
                    <span className="absolute -bottom-px -right-px text-primary text-sm">
                      ┘
                    </span>
                    <div className="flex items-center gap-2 p-3">
                      <span className="text-primary font-medium">&gt;</span>
                      <input
                        type="text"
                        value={urlB}
                        onChange={(e) => setUrlB(e.target.value)}
                        onFocus={() => setFocusedInput("b")}
                        onBlur={() => setFocusedInput(null)}
                        placeholder="github.com/teammate-b/repo or username"
                        className="flex-1 bg-transparent border-none outline-none text-foreground placeholder:text-muted-foreground/50 font-mono text-sm"
                      />
                      {focusedInput === "b" && (
                        <span className="w-2 h-4 bg-primary cursor-blink" />
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Submit button */}
              <div className="flex justify-center mt-6">
                <button
                  type="submit"
                  disabled={!hasAnyInput}
                  className={cn(
                    "w-3/5 border border-primary bg-primary/10 text-primary py-2.5 px-6",
                    "uppercase tracking-widest text-xs font-medium",
                    "transition-all duration-300",
                    "hover:bg-primary hover:text-primary-foreground",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                    "relative group"
                  )}
                >
                  <span className="absolute -top-px -left-px text-primary group-hover:text-primary-foreground text-xs">
                    ┌
                  </span>
                  <span className="absolute -top-px -right-px text-primary group-hover:text-primary-foreground text-xs">
                    ┐
                  </span>
                  <span className="absolute -bottom-px -left-px text-primary group-hover:text-primary-foreground text-xs">
                    └
                  </span>
                  <span className="absolute -bottom-px -right-px text-primary group-hover:text-primary-foreground text-xs">
                    ┘
                  </span>
                  {hasBothValid
                    ? "[ run duo scan ]"
                    : hasSingleValid
                      ? "[ run solo scan ]"
                      : "[ analyze ]"}
                </button>
              </div>

              {/* Example pairs */}
              <div className="flex items-center gap-3 mt-5 max-w-sm mx-auto">
                <div className="flex-1 border-t border-border/50" />
                <span className="text-xs text-muted-foreground uppercase tracking-widest">
                  or try an example pair
                </span>
                <div className="flex-1 border-t border-border/50" />
              </div>

              <div className="mt-3 flex justify-center gap-3">
                {DUO_EXAMPLES.map((ex) => (
                  <button
                    key={ex.label}
                    type="button"
                    onClick={() => handleExample(ex.urlA, ex.urlB)}
                    className={cn(
                      "border border-primary/50 bg-transparent text-primary/80 py-1.5 px-3",
                      "uppercase tracking-widest text-[10px] font-medium",
                      "transition-all duration-300",
                      "hover:border-primary hover:text-primary hover:bg-primary/5",
                      "relative group"
                    )}
                  >
                    <span className="absolute -top-px -left-px text-primary/50 group-hover:text-primary text-xs">
                      ┌
                    </span>
                    <span className="absolute -top-px -right-px text-primary/50 group-hover:text-primary text-xs">
                      ┐
                    </span>
                    <span className="absolute -bottom-px -left-px text-primary/50 group-hover:text-primary text-xs">
                      └
                    </span>
                    <span className="absolute -bottom-px -right-px text-primary/50 group-hover:text-primary text-xs">
                      ┘
                    </span>
                    [ {ex.label} ]
                  </button>
                ))}
              </div>
            </form>
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
