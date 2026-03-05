import { useState } from "react";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { TerminalInput } from "@/components/TerminalInput";
import { type PriorityKey } from "@/services/api";
import { api, type ProfileEvaluationResponse } from "@/services/api";
import { cn } from "@/utils/utils";

const HackerPage = () => {
  const [loading, setLoading] = useState(false);
  const [profileData, setProfileData] = useState<ProfileEvaluationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (input: string, _priorities: PriorityKey[]) => {
    const username = input.trim().toLowerCase();

    if (!username || username.length === 0) {
      setError("Please enter a valid GitHub username.");
      return;
    }

    // Basic validation: GitHub usernames are alphanumeric, dashes, and underscores
    if (!/^[a-z0-9_-]+$/i.test(username)) {
      setError("Invalid GitHub username format.");
      return;
    }

    if (typeof gtag !== "undefined") {
      gtag("event", "profile_evaluation_started", {
        event_category: "engagement",
        portal: "hacker",
        username: username,
      });
    }

    setLoading(true);
    setError(null);
    setProfileData(null);

    api
      .evaluateProfile(username)
      .then((data) => {
        setProfileData(data);
        setLoading(false);

        if (typeof gtag !== "undefined") {
          gtag("event", "profile_evaluation_completed", {
            event_category: "engagement",
            portal: "hacker",
            username: username,
            tier: data.tier,
          });
        }
      })
      .catch((err) => {
        setError(err.message || "Failed to evaluate profile. Please try again.");
        setLoading(false);

        if (typeof gtag !== "undefined") {
          gtag("event", "profile_evaluation_failed", {
            event_category: "error",
            portal: "hacker",
            username: username,
            error_message: err.message,
          });
        }
      });
  };

  // Map tier to color and display label
  const getTierColor = (tier: string) => {
    const tierMap: Record<string, { bg: string; text: string; border: string }> = {
      S: { bg: "from-yellow-500 to-amber-500", text: "text-yellow-100", border: "border-yellow-500" },
      A: { bg: "from-green-500 to-emerald-500", text: "text-green-100", border: "border-green-500" },
      B: { bg: "from-blue-500 to-cyan-500", text: "text-blue-100", border: "border-blue-500" },
      C: { bg: "from-purple-500 to-violet-500", text: "text-purple-100", border: "border-purple-500" },
      D: { bg: "from-orange-500 to-red-500", text: "text-orange-100", border: "border-orange-500" },
      F: { bg: "from-red-700 to-black", text: "text-red-100", border: "border-red-700" },
    };
    return tierMap[tier] || tierMap.C;
  };

  const getTierDescription = (tier: string): string => {
    const descriptions: Record<string, string> = {
      S: "Exceptional engineering excellence",
      A: "Strong developer, high quality work",
      B: "Good skills, room for growth",
      C: "Mixed signals, needs improvement",
      D: "Below average, notable concerns",
      F: "Critical issues, pure AI slop",
    };
    return descriptions[tier] || "Assessment pending";
  };

  const calculateAverageScore = (): number => {
    if (!profileData || profileData.repo_analyses.length === 0) return 0;
    const validScores = profileData.repo_analyses
      .map((r) => r.general_score)
      .filter((s) => s !== null && s !== undefined) as number[];
    if (validScores.length === 0) return 0;
    return Math.round(validScores.reduce((a, b) => a + b, 0) / validScores.length);
  };

  return (
    <GridBackground>
      <div className="flex flex-col min-h-screen">
        <Header />

        <main className="container mx-auto px-4 py-12">
          {!profileData && (
            <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
              <div className="text-center mb-12 max-w-2xl">
                <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                  Rate the player,
                  <br />
                  <span style={{ color: "hsl(var(--hacker))" }}>not the resume.</span>
                </h1>
                <p className="text-muted-foreground">
                  Enter a GitHub username. We'll analyze their top repos and give you a tier-based assessment.
                </p>
              </div>

              <h2
                className="text-xl md:text-2xl font-bold mb-6 uppercase tracking-widest"
                style={{ color: "hsl(var(--hacker))" }}
              >
                Profile Evaluation
              </h2>

              {/* Scope the hacker theme */}
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
                  placeholder="github_username"
                  isLoading={loading}
                  hidePriorities
                  submitLabel={loading ? "[ evaluating... ]" : "[ evaluate profile ]"}
                  examples={[
                    { label: "Torvalds", url: "torvalds" },
                    { label: "DHH", url: "dhh" },
                    { label: "Gvanrossum", url: "gvanrossum" },
                  ]}
                />
              </div>

              {error && (
                <div className="mt-8 p-4 border border-red-500 bg-red-500/10 text-red-200 rounded max-w-md text-center">
                  <p className="text-sm font-mono">{error}</p>
                </div>
              )}
            </div>
          )}

          {profileData && (
            <div className="animate-fade-in-up">
              {/* Header with back button */}
              <div className="flex items-center justify-between mb-8">
                <button
                  onClick={() => {
                    setProfileData(null);
                    setError(null);
                  }}
                  className="text-primary hover:text-primary/80 transition-colors text-sm uppercase tracking-widest font-mono"
                >
                  ← Back
                </button>
                <h1 className="text-2xl font-bold text-foreground">
                  @{profileData.username}
                </h1>
                <div className="w-16" />
              </div>

              {/* Main Report Card */}
              <div className="max-w-4xl mx-auto mb-8">
                <div className="border border-border bg-card/80 backdrop-blur-sm">
                  {/* Tier Section */}
                  <div className={cn(
                    "bg-gradient-to-r p-12 text-center",
                    getTierColor(profileData.tier).bg
                  )}>
                    <div className="text-sm uppercase tracking-widest text-white/80 mb-2">Overall Tier</div>
                    <div className={cn(
                      "text-9xl font-bold mb-4",
                      getTierColor(profileData.tier).text
                    )}>
                      {profileData.tier}
                    </div>
                    <p className="text-white/90 text-lg font-semibold">
                      {getTierDescription(profileData.tier)}
                    </p>
                  </div>

                  {/* Scores Section */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-8 border-t border-border">
                    <div className="border border-border/50 p-6 bg-muted/30">
                      <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
                        Average Score
                      </div>
                      <div className="text-5xl font-bold text-foreground mb-2">
                        {calculateAverageScore()}
                        <span className="text-2xl text-muted-foreground">/100</span>
                      </div>
                      <div className="w-full bg-border h-1.5 mt-4">
                        <div
                          className="bg-primary h-full transition-all"
                          style={{ width: `${calculateAverageScore()}%` }}
                        />
                      </div>
                    </div>

                    <div className="border border-border/50 p-6 bg-muted/30">
                      <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
                        Repos Analyzed
                      </div>
                      <div className="text-5xl font-bold text-foreground mb-4">
                        {profileData.repo_analyses.length}
                      </div>
                      <div className="space-y-1.5 mb-4">
                        {profileData.repo_analyses.map((repo) => (
                          <a
                            key={repo.url}
                            href={repo.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-primary hover:text-primary/80 transition-colors break-all flex items-start gap-1"
                          >
                            <span className="flex-shrink-0 mt-0.5">
                              {repo.is_pinned ? "📌" : "→"}
                            </span>
                            <span>{repo.name}</span>
                          </a>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground border-t border-border/30 pt-3">
                        Pinned repositories are prioritized in profile assessment as they represent the developer's best work.
                      </p>
                    </div>
                  </div>

                  {/* Justification Section */}
                  <div className="p-8 border-t border-border bg-muted/20">
                    <h3 className="text-lg font-bold mb-4 uppercase tracking-widest">Assessment</h3>
                    <ul className="space-y-2">
                      {profileData.profile_summary
                        .split("\n")
                        .map((line) => line.replace(/^•\s*/, "").trim())
                        .filter(Boolean)
                        .map((line, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                            <span className="text-primary flex-shrink-0 mt-0.5">•</span>
                            <span>{line}</span>
                          </li>
                        ))}
                    </ul>
                  </div>

                  {/* Individual Repos */}
                  <div className="p-8 border-t border-border">
                    <h3 className="text-lg font-bold mb-6 uppercase tracking-widest">Repository Breakdown</h3>
                    <div className="space-y-4">
                      {profileData.repo_analyses.map((repo) => (
                        <div key={repo.url} className="border border-border/50 p-4 bg-muted/30">
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <a
                                  href={repo.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-semibold text-foreground hover:text-primary transition-colors"
                                >
                                  {repo.name}
                                </a>
                                {repo.is_pinned && (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/20 border border-primary/50 rounded text-xs font-medium text-primary uppercase tracking-widest">
                                    📌 Pinned
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">{repo.url}</p>
                            </div>
                            <div className="text-right">
                              <div className="text-2xl font-bold text-primary">
                                {repo.general_score ?? "N/A"}
                              </div>
                              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                                {repo.verdict}
                              </p>
                            </div>
                          </div>

                          {/* Score breakdown */}
                          <div className="grid grid-cols-3 gap-3 mb-3">
                            <div className="text-center border-r border-border/30">
                              <div className="text-xs text-muted-foreground uppercase">AI Slop</div>
                              <div className="text-sm font-semibold text-foreground">{repo.ai_slop_score}</div>
                            </div>
                            <div className="text-center border-r border-border/30">
                              <div className="text-xs text-muted-foreground uppercase">Bad Practices</div>
                              <div className="text-sm font-semibold text-foreground">{repo.bad_practices_score}</div>
                            </div>
                            <div className="text-center">
                              <div className="text-xs text-muted-foreground uppercase">Quality</div>
                              <div className="text-sm font-semibold text-foreground">{repo.code_quality_score}</div>
                            </div>
                          </div>

                          {repo.repo_id && (
                            <a
                              href={`/repo/${repo.repo_id}`}
                              className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors uppercase tracking-widest font-mono"
                            >
                              → View Full Analysis
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex justify-center gap-4 mb-8">
                <button
                  onClick={() => {
                    setProfileData(null);
                    setError(null);
                  }}
                  className="border border-primary bg-primary/10 text-primary px-6 py-2 uppercase tracking-widest text-xs font-medium hover:bg-primary hover:text-primary-foreground transition-all"
                >
                  [ Evaluate Another ]
                </button>
                <a
                  href={`https://github.com/${profileData.username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="border border-primary/50 bg-transparent text-primary/80 px-6 py-2 uppercase tracking-widest text-xs font-medium hover:border-primary hover:text-primary hover:bg-primary/5 transition-all"
                >
                  [ View on GitHub ]
                </a>
              </div>
            </div>
          )}
        </main>

        <footer className="border-t border-border py-6 mt-auto">
          <p className="text-center text-xs text-muted-foreground uppercase tracking-widest font-mono">
            Built to filter signal from noise.
          </p>
        </footer>
      </div>
    </GridBackground>
  );
};

export default HackerPage;
