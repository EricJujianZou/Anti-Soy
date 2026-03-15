import { useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Header } from "@/components/Header";
import { useCandidateDetail } from "@/hooks/useCandidateDetail";
import type { CandidateRepoDetail, TechStackLanguage } from "@/services/batchApi";
import { generateBatchInterviewQuestions } from "@/services/batchApi";
import type { Finding, InterviewQuestion } from "@/services/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/utils/utils";
import { ChevronDown, ExternalLink, Github, ArrowLeft, Loader2, AlertCircle, Sparkles } from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
// CircularScore — inline SVG progress ring + centred score text
// ─────────────────────────────────────────────────────────────────────────────

const CircularScore = ({ score, size = 64 }: { score: number; size?: number }) => {
  const sw = 5;
  const r = (size - sw * 2) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (Math.min(Math.max(score, 0), 100) / 100) * circumference;
  const mid = size / 2;
  const fontSize = size >= 80 ? "1.125rem" : size >= 60 ? "0.8rem" : "0.65rem";

  return (
    <div
      className="relative flex items-center justify-center flex-shrink-0"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="absolute -rotate-90" aria-hidden>
        <circle
          cx={mid} cy={mid} r={r}
          fill="none" stroke="hsl(var(--muted))" strokeWidth={sw}
        />
        <circle
          cx={mid} cy={mid} r={r}
          fill="none" stroke="hsl(var(--primary))" strokeWidth={sw}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span
        className="relative z-10 font-bold font-mono text-primary tabular-nums"
        style={{ fontSize }}
      >
        {score}
      </span>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// FindingRow
// ─────────────────────────────────────────────────────────────────────────────

const SeverityLabel = ({ severity }: { severity: string }) => {
  const cls =
    severity === "critical"
      ? "text-destructive"
      : severity === "warning"
        ? "text-amber-500"
        : "text-muted-foreground";
  return (
    <span className={cn("text-[10px] font-bold uppercase tracking-widest flex-shrink-0", cls)}>
      {severity}
    </span>
  );
};

const FindingRow = ({ finding }: { finding: Finding }) => (
  <div className="py-2.5 border-b border-border/40 last:border-0 space-y-1.5">
    <div className="flex items-center gap-2 flex-wrap">
      <SeverityLabel severity={finding.severity} />
      <code className="text-[11px] text-muted-foreground font-mono">
        {finding.file}:{finding.line}
      </code>
    </div>
    <p className="text-sm text-foreground">{finding.explanation}</p>
    {finding.snippet && (
      <pre className="text-xs bg-muted/30 rounded p-2 font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap break-words max-h-28">
        {finding.snippet.slice(0, 300)}
      </pre>
    )}
  </div>
);

// ─────────────────────────────────────────────────────────────────────────────
// TechStackBreakdown
// ─────────────────────────────────────────────────────────────────────────────

const TechStackBreakdown = ({ breakdown }: { breakdown: TechStackLanguage[] }) => {
  if (!breakdown || breakdown.length === 0) return null;

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs font-bold uppercase tracking-widest text-primary">Tech Stack Breakdown</span>
        <div className="flex-1 border-t border-border/30" />
      </div>
      <Card className="border-border bg-card/50">
        <CardContent className="pt-4 space-y-3">
          {breakdown.map((entry) => {
            const total = entry.total_projects;
            const handPct = total > 0 ? (entry.hand_coded / total) * 100 : 0;
            const vibePct = total > 0 ? (entry.vibe_coded / total) * 100 : 0;
            return (
              <div key={entry.language} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-mono font-bold text-foreground">{entry.language}</span>
                  <span className="text-xs text-muted-foreground">
                    {total} project{total !== 1 ? "s" : ""}
                    {" · "}
                    <span className="text-green-500">{entry.hand_coded} hand-coded</span>
                    {entry.vibe_coded > 0 && (
                      <>, <span className="text-amber-500">{entry.vibe_coded} vibe-coded</span></>
                    )}
                  </span>
                </div>
                {/* Stacked bar */}
                <div className="h-2 rounded-full overflow-hidden bg-muted flex">
                  {handPct > 0 && (
                    <div
                      className="h-full bg-green-500 transition-all"
                      style={{ width: `${handPct}%` }}
                    />
                  )}
                  {vibePct > 0 && (
                    <div
                      className="h-full bg-amber-500 transition-all"
                      style={{ width: `${vibePct}%` }}
                    />
                  )}
                </div>
              </div>
            );
          })}
          <div className="flex items-center gap-4 pt-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" /> Hand-coded
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Vibe-coded (AI ≥ 60)
            </span>
          </div>
        </CardContent>
      </Card>
    </section>
  );
};


// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const PROJECT_TYPE_MAP: Record<string, string> = {
  real_problem: "Real Problem",
  tutorial: "Tutorial",
  portfolio_demo: "Portfolio Demo",
  learning_exercise: "Learning Exercise",
  utility_tool: "Utility Tool",
  library: "Library",
};

const CATEGORY_BADGE: Record<string, string> = {
  business_value: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  design_choice: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  code_issue: "bg-destructive/10 text-destructive border-destructive/20",
  technical_depth: "bg-primary/10 text-primary border-primary/20",
};

// ─────────────────────────────────────────────────────────────────────────────
// ProjectCard
// ─────────────────────────────────────────────────────────────────────────────

const ProjectCard = ({ repo }: { repo: CandidateRepoDetail }) => {
  const bv = repo.evaluation.business_value;
  const ai = repo.analysis.ai_slop;
  const bp = repo.analysis.bad_practices;
  const cq = repo.analysis.code_quality;
  const criticalBP = bp.findings.filter((f) => f.severity === "critical");
  const otherBP = bp.findings.filter((f) => f.severity !== "critical");

  return (
    <Card className="flex flex-col border-border bg-card/50 backdrop-blur-sm">
      {/* ── Header: repo name + per-repo score ──────────────────────────── */}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-bold font-mono text-foreground truncate">
              {repo.repo_name}
            </h3>
            <a
              href={repo.repo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 mt-0.5"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="w-3 h-3 flex-shrink-0" />
              <span className="truncate">{repo.repo_url.replace("https://github.com/", "")}</span>
            </a>
          </div>
          <CircularScore score={repo.overall_score} size={60} />
        </div>
      </CardHeader>

      <CardContent className="flex-1 space-y-4 text-sm">
        {/* ── Summary ─────────────────────────────────────────────────────── */}
        <p className="text-muted-foreground leading-relaxed">
          {bv.project_summary ||
            (repo.evaluation.standout_features.length > 0
              ? repo.evaluation.standout_features[0]
              : "Nothing particularly stands out about this project.")}
        </p>

        {/* ── Does the Code Back It Up? ────────────────────────────────── */}
        <div className="rounded-lg border border-border/60 bg-muted/10 p-4 space-y-3">
          <h4 className="font-bold text-foreground">Does the Code Back It Up?</h4>

          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Project Type</p>
              <p className="font-mono font-bold text-sm">
                {PROJECT_TYPE_MAP[bv.project_type] ?? bv.project_type}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Solves Real Problem?</p>
              <Badge
                className={cn(
                  "font-bold text-xs uppercase tracking-widest rounded-full px-3",
                  bv.solves_real_problem
                    ? "bg-primary text-primary-foreground hover:bg-primary"
                    : "bg-muted text-muted-foreground hover:bg-muted",
                )}
              >
                {bv.solves_real_problem ? "Yes" : "No"}
              </Badge>
            </div>
          </div>

          <div>
            <p className="text-xs text-muted-foreground mb-1">What It Claims To Do</p>
            <p className="font-mono font-bold text-sm">{bv.project_description}</p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground mb-1">Originality Assessment</p>
            <p className="font-mono text-sm">{bv.originality_assessment}</p>
          </div>
        </div>

        {/* ── AI Usage collapsible ─────────────────────────────────────── */}
        <Collapsible>
          <div className="rounded-lg border border-border/60 overflow-hidden">
            <CollapsibleTrigger className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors text-left">
              <div className="flex items-center gap-3">
                <span className="font-bold font-mono text-sm">AI Usage</span>
                <Badge variant="outline" className="font-mono text-xs tabular-nums">
                  {ai.score}/100
                </Badge>
                <span className="text-xs text-muted-foreground">{ai.confidence} confidence</span>
              </div>
              <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            </CollapsibleTrigger>
            <CollapsibleContent className="px-4 pb-4 pt-1">
              {ai.negative_ai_signals.length === 0 && ai.positive_ai_signals.length === 0 ? (
                <p className="text-xs text-muted-foreground py-1">
                  No significant AI signals detected.
                </p>
              ) : (
                <div className="space-y-3">
                  {ai.negative_ai_signals.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
                        AI Signals Detected
                      </p>
                      {ai.negative_ai_signals.map((s, i) => (
                        <FindingRow key={i} finding={s} />
                      ))}
                    </div>
                  )}
                  {ai.positive_ai_signals.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2">
                        Positive Signals
                      </p>
                      {ai.positive_ai_signals.map((s, i) => (
                        <div
                          key={i}
                          className="text-sm text-foreground py-1.5 border-b border-border/40 last:border-0"
                        >
                          {s.explanation}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CollapsibleContent>
          </div>
        </Collapsible>

        {/* ── Deep Dive collapsible ────────────────────────────────────── */}
        <Collapsible>
          <div className="rounded-lg border border-border/60 overflow-hidden">
            <CollapsibleTrigger className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/20 transition-colors text-left">
              <span className="font-bold font-mono text-sm">Deep Dive</span>
              <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            </CollapsibleTrigger>
            <CollapsibleContent className="px-4 pb-4 pt-1 space-y-5">
              {/* Code Quality */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    Code Quality
                  </p>
                  <Badge variant="outline" className="font-mono text-xs">
                    {cq.score}/100
                  </Badge>
                </div>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {(
                    [
                      { label: "Files", val: cq.files_organized },
                      { label: "README", val: cq.readme_quality },
                      { label: "Deps", val: cq.dependency_health },
                    ] as const
                  ).map(({ label, val }) => (
                    <div key={label} className="rounded bg-muted/20 p-2 text-center">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-widest">
                        {label}
                      </p>
                      <p className="text-sm font-bold font-mono text-primary">{val}</p>
                    </div>
                  ))}
                </div>
                {cq.findings.slice(0, 4).map((f, i) => (
                  <FindingRow key={i} finding={f} />
                ))}
              </div>

              {/* Bad Practices */}
              {(criticalBP.length > 0 || otherBP.length > 0) && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                      Bad Practices
                    </p>
                    <Badge variant="outline" className="font-mono text-xs">
                      {bp.score}/100
                    </Badge>
                    {bp.security_issues > 0 && (
                      <Badge
                        variant="outline"
                        className="text-xs bg-destructive/10 text-destructive border-destructive/20"
                      >
                        {bp.security_issues} security
                      </Badge>
                    )}
                  </div>
                  {criticalBP.map((f, i) => (
                    <FindingRow key={`c-${i}`} finding={f} />
                  ))}
                  {otherBP.slice(0, 3).map((f, i) => (
                    <FindingRow key={`o-${i}`} finding={f} />
                  ))}
                </div>
              )}
            </CollapsibleContent>
          </div>
        </Collapsible>
      </CardContent>
    </Card>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

const CandidateAssessment = () => {
  const { batchId, itemId } = useParams<{ batchId: string; itemId: string }>();
  const navigate = useNavigate();
  const { data, isLoading, error } = useCandidateDetail(batchId ?? "", itemId ?? "");

  const [generatedQuestions, setGeneratedQuestions] = useState<InterviewQuestion[] | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Use stored questions from BatchItem, overridden by freshly generated ones
  const displayedQuestions: InterviewQuestion[] | null = generatedQuestions ?? data?.interview_questions ?? null;

  const handleGenerate = async () => {
    if (!batchId || !itemId) return;
    setIsGenerating(true);
    setGenerateError(null);
    try {
      const result = await generateBatchInterviewQuestions(batchId, Number(itemId));
      setGeneratedQuestions(result.interview_questions);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Failed to generate questions");
    } finally {
      setIsGenerating(false);
    }
  };

  // Legacy aggregation kept as fallback for old items that still have per-repo questions
  const legacyQuestions = useMemo<(InterviewQuestion & { repoName: string })[]>(() => {
    if (!data || displayedQuestions !== null) return [];
    return data.repos.flatMap((repo) =>
      (repo.evaluation.interview_questions ?? []).map((q) => ({
        ...q,
        repoName: repo.repo_name,
      })),
    );
  }, [data, displayedQuestions]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container mx-auto px-4 py-12 flex items-center justify-center min-h-[60vh] gap-3 text-muted-foreground">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm uppercase tracking-widest">Loading candidate data...</span>
        </main>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container mx-auto px-4 py-12 text-center">
          <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-bold uppercase tracking-widest mb-2">
            Could Not Load Candidate
          </h2>
          <p className="text-muted-foreground mb-8">{error?.message ?? "Unknown error"}</p>
          <Button variant="outline" onClick={() => navigate(`/dashboard/${batchId}`)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-12 space-y-12">
        {/* Back nav */}
        <button
          onClick={() => navigate(`/dashboard/${batchId}`)}
          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors uppercase tracking-widest"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Dashboard
        </button>

        {/* ── Candidate header ──────────────────────────────────────────── */}
        <div className="flex items-center gap-6">
          <CircularScore score={data.overall_score} size={88} />
          <div>
            <h1 className="text-3xl font-bold text-foreground uppercase tracking-widest">
              {data.candidate_name}
            </h1>
            {data.github_profile_url && (
              <a
                href={data.github_profile_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-1.5 mt-1"
              >
                <Github className="w-4 h-4" />
                {data.github_profile_url}
              </a>
            )}
          </div>
        </div>

        {/* ── Tech Stack Breakdown ──────────────────────────────────────── */}
        {data.tech_stack_breakdown && data.tech_stack_breakdown.length > 0 && (
          <TechStackBreakdown breakdown={data.tech_stack_breakdown} />
        )}

        {/* ── Project Assessments ────────────────────────────────────────── */}
        <section>
          <div className="flex items-baseline gap-3 mb-6">
            <h2 className="text-xl font-bold uppercase tracking-widest">Project Assessments</h2>
            <span className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
              Displaying {data.repos.length} verified repo{data.repos.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {data.repos.map((repo) => (
              <ProjectCard key={repo.repo_id} repo={repo} />
            ))}
          </div>
        </section>

        {/* ── Interview Questions (aggregated across all repos) ─────────── */}
        <section>
          {displayedQuestions !== null && displayedQuestions.length > 0 ? (
            // Stored or freshly-generated questions
            <Collapsible defaultOpen>
              <Card className="border-border">
                <CollapsibleTrigger asChild>
                  <CardHeader className="cursor-pointer hover:bg-muted/20 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <CardTitle className="text-lg uppercase tracking-widest">
                          Interview Questions
                        </CardTitle>
                        <Badge variant="outline" className="font-mono tabular-nums">
                          {displayedQuestions.length}
                        </Badge>
                      </div>
                      <ChevronDown className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </CardHeader>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <CardContent className="pt-0 space-y-5">
                    {displayedQuestions.map((q, i) => (
                      <div
                        key={i}
                        className="border-b border-border/40 pb-5 last:border-0 last:pb-0"
                      >
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[10px] uppercase tracking-widest font-bold",
                              CATEGORY_BADGE[q.category] ?? "",
                            )}
                          >
                            {q.category.replace(/_/g, " ")}
                          </Badge>
                        </div>
                        <p className="text-sm font-medium text-foreground mb-2">{q.question}</p>
                        <div className="flex flex-wrap gap-x-4 gap-y-1">
                          <p className="text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground/70">Based on:</span>{" "}
                            {q.based_on}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground/70">Probes:</span>{" "}
                            {q.probes}
                          </p>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </CollapsibleContent>
              </Card>
            </Collapsible>
          ) : legacyQuestions.length > 0 ? (
            // Fallback: old per-repo questions for pre-migration items
            <Collapsible defaultOpen>
              <Card className="border-border">
                <CollapsibleTrigger asChild>
                  <CardHeader className="cursor-pointer hover:bg-muted/20 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <CardTitle className="text-lg uppercase tracking-widest">
                          Interview Questions
                        </CardTitle>
                        <Badge variant="outline" className="font-mono tabular-nums">
                          {legacyQuestions.length}
                        </Badge>
                      </div>
                      <ChevronDown className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </CardHeader>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <CardContent className="pt-0 space-y-5">
                    {legacyQuestions.map((q, i) => (
                      <div
                        key={i}
                        className="border-b border-border/40 pb-5 last:border-0 last:pb-0"
                      >
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[10px] uppercase tracking-widest font-bold",
                              CATEGORY_BADGE[q.category] ?? "",
                            )}
                          >
                            {q.category.replace(/_/g, " ")}
                          </Badge>
                          <span className="text-[10px] text-muted-foreground font-mono uppercase tracking-widest">
                            re: {q.repoName}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-foreground mb-2">{q.question}</p>
                        <div className="flex flex-wrap gap-x-4 gap-y-1">
                          <p className="text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground/70">Based on:</span>{" "}
                            {q.based_on}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground/70">Probes:</span>{" "}
                            {q.probes}
                          </p>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </CollapsibleContent>
              </Card>
            </Collapsible>
          ) : (
            // Not yet generated — show Generate button
            <Card className="border-border border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-10 gap-4">
                <p className="text-sm text-muted-foreground uppercase tracking-widest">
                  Interview Questions
                </p>
                <p className="text-xs text-muted-foreground text-center max-w-xs">
                  Generate 3–5 tailored questions based on all of{" "}
                  {data.candidate_name}’s analyzed projects.
                </p>
                {generateError && (
                  <p className="text-xs text-destructive">{generateError}</p>
                )}
                <Button
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="gap-2"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Generate Interview Questions
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          )}
        </section>
      </main>
    </div>
  );
};

export default CandidateAssessment;
