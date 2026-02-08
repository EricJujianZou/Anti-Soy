import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { ProgressTracker } from "@/components/ProgressTracker";
import { useAnalyzeStream } from "@/hooks/useAnalyzeStream";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  ChevronDown,
  XCircle,
  AlertTriangle,
  Bot,
  MessageSquare,
  FileCode,
  Loader2,
} from "lucide-react";
import type {
  AnalysisResponse,
  EvaluationEvent,
  InterviewQuestion,
} from "@/services/api";

function getRepoName(githubLink: string): string {
  const parts = githubLink.replace(/\/$/, "").split("/");
  return parts[parts.length - 1] || "Unknown";
}

const RepoAnalysis = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const [searchParams] = useSearchParams();
  const repoLink = searchParams.get("link");

  const {
    error,
    analysis,
    evaluation,
    questions,
    questionsError,
    startStream,
  } = useAnalyzeStream();

  const [hasStarted, setHasStarted] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState<
    "idle" | "submitting" | "success" | "error"
  >("idle");
  const feedbackRef = useRef<HTMLDivElement>(null);

  const scrollToFeedback = () => {
    feedbackRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (repoLink && !hasStarted) {
      setHasStarted(true);
      startStream(repoLink);
    }
  }, [repoLink, hasStarted, startStream]);

  const repoName = repoLink ? getRepoName(repoLink) : repoId || "Unknown";

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

  const renderLoading = () => (
    <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Analyzing <span className="text-primary">{repoName}</span>
        </h2>
        <p className="text-sm text-muted-foreground">
          Running deeper metrics and signal checks...
        </p>
        {error && (
          <p className="text-sm text-red-500 mt-2">Error: {error}</p>
        )}
      </div>
      <ProgressTracker steps={[]} className="w-full max-w-md" />
    </div>
  );

  const handleFeedbackSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFeedbackStatus("submitting");

    const formData = new FormData(e.currentTarget);
    const data = Object.fromEntries(formData);

    try {
      const response = await fetch(`https://formspree.io/f/maqdyrqz`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });
      if (response.ok) setFeedbackStatus("success");
      else setFeedbackStatus("error");
    } catch {
      setFeedbackStatus("error");
    }
  };

  const renderResults = (
    analysis: AnalysisResponse,
    evaluation: EvaluationEvent | null,
    questions: InterviewQuestion[] | null,
    questionsError: string | null,
  ) => {
    const criticalFindings = analysis.bad_practices.findings.filter(
      (f) => f.severity === "critical",
    );
    const nonCriticalFindings = analysis.bad_practices.findings.filter(
      (f) => f.severity !== "critical",
    );
    const standoutFeatures =
      evaluation?.standout_features?.filter((f) => f.trim()) ?? [];
    const hasStandout = standoutFeatures.length > 0;
    const evalLoaded = evaluation !== null;
    const questionsLoaded = questions !== null;

    return (
      <div className="animate-fade-in-up space-y-6 max-w-3xl mx-auto">
        {/* ====== SECTION 1: VERDICT BANNER ====== */}
        <div>
          {!evalLoaded ? (
            // LLM still loading — show static verdict + spinner
            <div className="rounded-lg border bg-muted/30 p-6">
              <div className="flex items-center gap-3">
                <Badge variant="outline">{analysis.verdict.type}</Badge>
                <span className="text-muted-foreground text-xs">
                  {analysis.verdict.confidence}% confidence
                </span>
              </div>
              <div className="flex items-center gap-2 mt-3 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Finalizing decision...</span>
              </div>
            </div>
          ) : hasStandout ? (
            <div className="rounded-lg border-2 border-primary bg-primary/5 p-6">
              <p className="text-xs uppercase tracking-widest text-muted-foreground mb-1">
                What Stands Out
              </p>
              <p className="text-2xl font-bold text-primary">
                {standoutFeatures.join(" · ")}
              </p>
            </div>
          ) : evaluation.is_rejected ? (
            <div className="rounded-lg border-2 border-destructive bg-destructive/10 p-6">
              <div className="flex items-center gap-3">
                <XCircle className="h-6 w-6 text-destructive flex-shrink-0" />
                <div>
                  <h2 className="text-xl font-bold text-destructive">
                    REJECT
                  </h2>
                  <p className="text-sm text-destructive/80 mt-1">
                    {evaluation.rejection_reason || "Critical issue found."}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border bg-muted/30 p-6">
              <p className="text-lg text-muted-foreground">
                Nothing particularly stands out about this project.
              </p>
            </div>
          )}

          {/* View Evidence */}
          <Collapsible>
            <CollapsibleTrigger className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mt-3 transition-colors">
              <ChevronDown className="h-3 w-3" />
              View Evidence
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 rounded-lg border bg-card p-4 space-y-3 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="outline">{analysis.verdict.type}</Badge>
                <span className="text-muted-foreground text-xs">
                  {analysis.verdict.confidence}% confidence
                </span>
                <span className="text-muted-foreground text-xs">
                  {analysis.files_analyzed.length} files scanned
                </span>
              </div>
              {analysis.ai_slop.negative_ai_signals.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Key AI Signals:
                  </p>
                  <ul className="space-y-1">
                    {analysis.ai_slop.negative_ai_signals
                      .slice(0, 3)
                      .map((s, i) => (
                        <li
                          key={i}
                          className="text-xs text-muted-foreground"
                        >
                          <span className="text-foreground">{s.type}</span>
                          {s.file && ` — ${s.file}:${s.line}`}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
              {evalLoaded && evaluation.business_value?.project_summary && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    LLM Summary:
                  </p>
                  <p className="text-sm">
                    {evaluation.business_value.project_summary}
                  </p>
                </div>
              )}
            </CollapsibleContent>
          </Collapsible>
        </div>

        {/* ====== SECTION 2: BUSINESS VALUE ====== */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              Does the Code Back It Up?
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {!evalLoaded || !evaluation.business_value ? (
              // Skeleton loader
              <div className="space-y-3 animate-pulse">
                <div className="grid grid-cols-2 gap-4">
                  <div className="h-10 bg-muted rounded" />
                  <div className="h-10 bg-muted rounded" />
                </div>
                <div className="h-6 bg-muted rounded w-3/4" />
                <div className="h-6 bg-muted rounded w-full" />
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-muted-foreground text-xs mb-0.5">
                      Project Type
                    </p>
                    <p className="font-medium capitalize">
                      {evaluation.business_value.project_type.replace(
                        /_/g,
                        " ",
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground text-xs mb-0.5">
                      Solves Real Problem?
                    </p>
                    <Badge
                      variant={
                        evaluation.business_value.solves_real_problem
                          ? "default"
                          : "secondary"
                      }
                    >
                      {evaluation.business_value.solves_real_problem
                        ? "Yes"
                        : "No"}
                    </Badge>
                  </div>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs mb-0.5">
                    What It Claims To Do
                  </p>
                  <p>{evaluation.business_value.project_description}</p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs mb-0.5">
                    Originality Assessment
                  </p>
                  <p>{evaluation.business_value.originality_assessment}</p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* ====== SECTION 3: AI USAGE (available immediately) ====== */}
        <Collapsible>
          <Card>
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors pb-3">
                <CardTitle className="text-base flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Bot className="h-4 w-4" />
                    AI Usage
                    <Badge
                      variant={
                        analysis.ai_slop.score > 60
                          ? "destructive"
                          : analysis.ai_slop.score > 30
                            ? "secondary"
                            : "outline"
                      }
                    >
                      {analysis.ai_slop.score}/100
                    </Badge>
                    <span className="text-xs text-muted-foreground font-normal">
                      {analysis.ai_slop.confidence} confidence
                    </span>
                  </span>
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent className="space-y-4 text-sm">
                {analysis.ai_slop.negative_ai_signals.length > 0 && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-2">
                      Red Flags
                    </p>
                    <div className="space-y-2">
                      {analysis.ai_slop.negative_ai_signals.map(
                        (signal, i) => (
                          <div key={i} className="flex items-start gap-2">
                            <span className="text-destructive mt-0.5 text-xs">
                              ✕
                            </span>
                            <div>
                              <span className="font-medium text-sm">
                                {signal.type}
                              </span>
                              {signal.file && (
                                <span className="text-muted-foreground text-xs ml-2">
                                  {signal.file}:{signal.line}
                                </span>
                              )}
                              <p className="text-xs text-muted-foreground">
                                {signal.explanation}
                              </p>
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
                {analysis.ai_slop.positive_ai_signals.length > 0 && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-2">
                      Good Signs
                    </p>
                    <div className="space-y-2">
                      {analysis.ai_slop.positive_ai_signals.map(
                        (signal, i) => (
                          <div key={i} className="flex items-start gap-2">
                            <span className="text-primary mt-0.5 text-xs">
                              ✓
                            </span>
                            <div>
                              <span className="font-medium text-sm">
                                {signal.type}
                              </span>
                              <p className="text-xs text-muted-foreground">
                                {signal.explanation}
                              </p>
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* ====== SECTION 4: DEEP DIVE (available immediately) ====== */}
        <Collapsible>
          <Card>
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors pb-3">
                <CardTitle className="text-base flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <FileCode className="h-4 w-4" />
                    Deep Dive
                  </span>
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent className="space-y-6">
                {/* Critical Issues */}
                {criticalFindings.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-destructive" />
                      Critical Issues ({criticalFindings.length})
                    </h4>
                    <div className="space-y-2">
                      {criticalFindings.map((finding, i) => (
                        <div
                          key={i}
                          className="rounded border border-destructive/20 bg-destructive/5 p-3 text-sm"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium">{finding.type}</span>
                            <span className="text-xs text-muted-foreground">
                              {finding.file}:{finding.line}
                            </span>
                          </div>
                          <p className="text-muted-foreground text-xs">
                            {finding.explanation}
                          </p>
                          {finding.snippet && (
                            <pre className="mt-2 rounded bg-background p-2 text-xs overflow-x-auto">
                              <code>{finding.snippet}</code>
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Bad Practices (non-critical) */}
                {nonCriticalFindings.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                      Bad Practices
                      <Badge variant="secondary">
                        {analysis.bad_practices.score}/100
                      </Badge>
                    </h4>
                    <div className="space-y-2">
                      {nonCriticalFindings.map((f, i) => (
                        <div key={i} className="rounded border p-2 text-xs">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge
                              variant={
                                f.severity === "warning"
                                  ? "secondary"
                                  : "outline"
                              }
                              className="text-xs"
                            >
                              {f.severity}
                            </Badge>
                            <span className="font-medium">{f.type}</span>
                            <span className="text-muted-foreground ml-auto">
                              {f.file}:{f.line}
                            </span>
                          </div>
                          <p className="text-muted-foreground">
                            {f.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Code Quality */}
                <div>
                  <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                    Code Quality
                    <Badge variant="secondary">
                      {analysis.code_quality.score}/100
                    </Badge>
                  </h4>
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div>
                      <p className="text-muted-foreground">Organization</p>
                      <p className="font-medium">
                        {analysis.code_quality.files_organized}%
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Test Coverage</p>
                      <p className="font-medium">
                        {analysis.code_quality.test_coverage}%
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">README</p>
                      <p className="font-medium">
                        {analysis.code_quality.readme_quality}%
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Error Handling</p>
                      <p className="font-medium">
                        {analysis.code_quality.error_handling}%
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Logging</p>
                      <p className="font-medium">
                        {analysis.code_quality.logging_quality}%
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Dependencies</p>
                      <p className="font-medium">
                        {analysis.code_quality.dependency_health}%
                      </p>
                    </div>
                  </div>
                  {analysis.code_quality.findings.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {analysis.code_quality.findings.map((f, i) => (
                        <div key={i} className="rounded border p-2 text-xs">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="text-xs">
                              {f.severity}
                            </Badge>
                            <span className="font-medium">{f.type}</span>
                            <span className="text-muted-foreground ml-auto">
                              {f.file}:{f.line}
                            </span>
                          </div>
                          <p className="text-muted-foreground">
                            {f.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Files Analyzed */}
                <div>
                  <h4 className="text-sm font-medium mb-2">
                    Files Analyzed ({analysis.files_analyzed.length})
                  </h4>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {analysis.files_analyzed.map((f, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between text-xs py-1 border-b last:border-0"
                      >
                        <span className="font-mono">{f.path}</span>
                        <span className="text-muted-foreground">
                          {f.loc} LOC
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* ====== SECTION 5: INTERVIEW QUESTIONS ====== */}
        <Collapsible>
          <Card>
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer hover:bg-muted/30 transition-colors pb-3">
                <CardTitle className="text-base flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    Interview Questions
                    {questionsLoaded && questions.length > 0 && (
                      <Badge variant="outline">{questions.length}</Badge>
                    )}
                  </span>
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent className="space-y-3">
                {!questionsLoaded ? (
                  <div className="flex items-center gap-2 py-4 justify-center text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">
                      Generating interview questions...
                    </span>
                  </div>
                ) : questionsError ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">
                    {questionsError}
                  </p>
                ) : questions.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">
                    No interview questions generated.
                  </p>
                ) : (
                  questions.map((q, i) => (
                    <div key={i} className="rounded border p-3">
                      <p className="font-medium text-sm mb-2">{q.question}</p>
                      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                        <div>
                          <span className="font-medium text-foreground">
                            Based on:{" "}
                          </span>
                          {q.based_on}
                        </div>
                        <div>
                          <span className="font-medium text-foreground">
                            Probes:{" "}
                          </span>
                          {q.probes}
                        </div>
                      </div>
                      <Badge variant="outline" className="mt-2 text-xs">
                        {q.category}
                      </Badge>
                    </div>
                  ))
                )}
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>

        {/* ====== SECTION 6: FEEDBACK FORM ====== */}
        <div ref={feedbackRef} className="pt-12 pb-8">
          <Card className="border-primary/20 bg-primary/5">
            <CardHeader>
              <CardTitle className="text-lg text-center">
                Feedback & Updates
              </CardTitle>
            </CardHeader>
            <CardContent>
              {feedbackStatus === "success" ? (
                <div className="text-center text-success py-8">
                  <p className="font-bold">Thank you for your feedback!</p>
                  <p className="text-sm text-muted-foreground">
                    We'll use it to improve the detection engine.
                  </p>
                </div>
              ) : (
                <form
                  onSubmit={handleFeedbackSubmit}
                  className="space-y-4 max-w-md mx-auto"
                >
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">
                      Email (optional)
                    </label>
                    <input
                      name="email"
                      type="email"
                      placeholder="you@example.com"
                      className="w-full bg-background border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">
                      Feedback
                    </label>
                    <textarea
                      name="message"
                      required
                      rows={3}
                      placeholder="What did we miss? Was this analysis accurate?"
                      className="w-full bg-background border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-primary resize-none"
                    ></textarea>
                  </div>
                  <button
                    type="submit"
                    disabled={feedbackStatus === "submitting"}
                    className="w-full bg-primary text-primary-foreground py-2 rounded text-sm font-bold hover:bg-primary/90 transition-colors"
                  >
                    {feedbackStatus === "submitting"
                      ? "Sending..."
                      : "Send Feedback"}
                  </button>
                </form>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  };

  return (
    <GridBackground>
      <Header />
      <main className="container mx-auto px-4 py-12">
        <div className="relative flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Link
                to="/"
                className="text-muted-foreground hover:text-foreground transition-colors text-sm"
              >
                ← Home
              </Link>
              <span className="text-muted-foreground">/</span>
              <h1 className="text-2xl font-bold text-foreground">
                <span className="text-primary text-glow">{repoName}</span>
              </h1>
            </div>
            <a
              href={repoLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground hover:text-primary transition-colors max-w-2xl break-all"
            >
              {repoLink}
            </a>
          </div>

          {/* Feedback Button - Only shows when results are ready */}
          {analysis && (
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden md:block">
              <button
                onClick={scrollToFeedback}
                className="bg-primary hover:bg-primary/90 text-primary-foreground px-6 py-2 rounded-full text-sm font-bold shadow-lg shadow-primary/20 transition-all hover:scale-105"
              >
                Give Feedback
              </button>
            </div>
          )}
        </div>
        {!analysis
          ? renderLoading()
          : renderResults(analysis, evaluation, questions, questionsError)}
      </main>
    </GridBackground>
  );
};

export default RepoAnalysis;
