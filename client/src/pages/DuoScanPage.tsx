import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { BarLoader } from "@/components/BarLoader";
import { RankCard } from "@/components/RankCard";
import { useAnalyzeStream } from "@/hooks/useAnalyzeStream";
import {
  fetchCompatibility,
  type CompatibilityResponse,
  type AnalysisResponse,
  type EvaluationEvent,
  type InterviewQuestion,
} from "@/services/api";
import { getTier, deriveTraits } from "@/utils/rankTier";
import { cn } from "@/utils/utils";
import { ChevronDown } from "lucide-react";

// =============================================================================
// Compatibility Block
// =============================================================================

function CompatibilityBlock({ compat }: { compat: CompatibilityResponse }) {
  const scoreColor =
    compat.score >= 80
      ? "#22c55e"
      : compat.score >= 60
        ? "#06b6d4"
        : compat.score >= 40
          ? "#f59e0b"
          : "#ef4444";

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6 animate-fade-in-up">
      {/* Score header */}
      <div className="text-center space-y-2">
        <h2
          className="text-lg uppercase tracking-widest font-bold"
          style={{ color: "hsl(var(--hacker))" }}
        >
          Compatibility Analysis
        </h2>
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Status: {compat.score_label}
        </p>
      </div>

      {/* Score bar */}
      <div className="space-y-2">
        <div className="flex items-baseline justify-center gap-2">
          <span
            className="text-5xl font-bold font-mono"
            style={{ color: scoreColor }}
          >
            {compat.score}
          </span>
          <span className="text-xl text-muted-foreground font-mono">%</span>
        </div>
        <div className="w-full max-w-md mx-auto h-2 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000 ease-out"
            style={{
              width: `${compat.score}%`,
              backgroundColor: scoreColor,
            }}
          />
        </div>
        <p className="text-center text-sm font-medium" style={{ color: scoreColor }}>
          {compat.score_label}
        </p>
      </div>

      {/* Strategic Advice */}
      {compat.narrative && (
        <div
          className="relative border p-4"
          style={{ borderColor: "hsl(var(--hacker) / 0.3)" }}
        >
          <span
            className="absolute -top-px -left-px text-sm"
            style={{ color: "hsl(var(--hacker))" }}
          >
            ┌
          </span>
          <span
            className="absolute -top-px -right-px text-sm"
            style={{ color: "hsl(var(--hacker))" }}
          >
            ┐
          </span>
          <span
            className="absolute -bottom-px -left-px text-sm"
            style={{ color: "hsl(var(--hacker))" }}
          >
            └
          </span>
          <span
            className="absolute -bottom-px -right-px text-sm"
            style={{ color: "hsl(var(--hacker))" }}
          >
            ┘
          </span>
          <h3
            className="text-xs uppercase tracking-widest font-bold mb-2"
            style={{ color: "hsl(var(--hacker))" }}
          >
            Strategic Advice
          </h3>
          <p className="text-sm text-muted-foreground italic leading-relaxed">
            {compat.narrative}
          </p>
        </div>
      )}

      {/* Callouts */}
      {compat.callouts.length > 0 && (
        <div className="space-y-2">
          {compat.callouts.map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <span
                className={cn(
                  "mt-0.5",
                  c.type === "strength" ? "text-green-400" : "text-amber-400"
                )}
              >
                {c.type === "strength" ? "✓" : "⚠"}
              </span>
              <span className="text-foreground/80">{c.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Profile Summary (side by side)
// =============================================================================

function ProfileSummary({
  label,
  analysis,
  evaluation,
}: {
  label: string;
  analysis: NonNullable<ReturnType<typeof useAnalyzeStream>["analysis"]>;
  evaluation: ReturnType<typeof useAnalyzeStream>["evaluation"];
}) {
  const tier = getTier(analysis, evaluation);
  const traits = deriveTraits(analysis, evaluation);

  return (
    <div className="flex flex-col items-center space-y-3">
      <div className="flex items-center gap-3">
        <img
          src={`https://github.com/${analysis.repo.owner}.png?size=48`}
          alt={analysis.repo.owner}
          className="w-10 h-10 rounded-full border-2"
          style={{ borderColor: tier.color }}
        />
        <div>
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground block">
            {label}
          </span>
          <span
            className="text-sm font-bold uppercase tracking-wider"
            style={{ color: tier.color }}
          >
            {tier.tier}
          </span>
          <span className="text-xs text-muted-foreground block">
            {analysis.repo.owner}/{analysis.repo.name}
          </span>
        </div>
      </div>
      <div className="space-y-1">
        {traits.map((t, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span style={{ color: tier.color }}>■</span>
            <span className="text-foreground/80">{t}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Loading Card placeholder
// =============================================================================

function LoadingCard({ label }: { label: string }) {
  return (
    <div className="w-[380px] border border-border bg-card/50 p-5 space-y-4 shrink-0">
      <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <div className="flex items-center justify-center py-8">
        <BarLoader />
      </div>
      <p className="text-xs text-muted-foreground text-center">
        Analyzing repository...
      </p>
    </div>
  );
}

function ErrorCard({ label, error }: { label: string; error: string }) {
  return (
    <div className="w-[380px] border border-red-500/50 bg-card/50 p-5 space-y-4 shrink-0">
      <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      <div className="py-8 text-center">
        <span className="text-red-400 text-sm">{error}</span>
      </div>
    </div>
  );
}

// =============================================================================
// Evidence Panel (deep dive for one person)
// =============================================================================

function EvidencePanel({
  label,
  analysis,
  evaluation,
  questions,
}: {
  label: string;
  analysis: AnalysisResponse;
  evaluation: EvaluationEvent | null;
  questions: InterviewQuestion[] | null;
}) {
  const criticalFindings = analysis.bad_practices.findings.filter(
    (f) => f.severity === "critical"
  );
  const nonCriticalFindings = analysis.bad_practices.findings.filter(
    (f) => f.severity !== "critical"
  );

  return (
    <div className="space-y-6 min-w-0">
      <h3
        className="text-xs uppercase tracking-widest font-bold"
        style={{ color: "hsl(var(--hacker))" }}
      >
        {label} — {analysis.repo.owner}/{analysis.repo.name}
      </h3>

      {/* AI Usage */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium flex items-center gap-2">
          AI Usage
          <span
            className={cn(
              "text-xs px-1.5 py-0.5 rounded-sm",
              analysis.ai_slop.score > 60
                ? "text-red-400 bg-red-400/10"
                : analysis.ai_slop.score > 30
                  ? "text-amber-400 bg-amber-400/10"
                  : "text-green-400 bg-green-400/10"
            )}
          >
            {analysis.ai_slop.score}/100
          </span>
        </h4>
        {analysis.ai_slop.negative_ai_signals.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Red Flags</p>
            <div className="space-y-2">
              {analysis.ai_slop.negative_ai_signals.map((signal, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-red-400 mt-0.5 text-xs">✕</span>
                  <div>
                    <span className="font-medium text-sm">{signal.type}</span>
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
              ))}
            </div>
          </div>
        )}
        {analysis.ai_slop.positive_ai_signals.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Good Signs</p>
            <div className="space-y-2">
              {analysis.ai_slop.positive_ai_signals.map((signal, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-green-400 mt-0.5 text-xs">✓</span>
                  <div>
                    <span className="font-medium text-sm">{signal.type}</span>
                    <p className="text-xs text-muted-foreground">
                      {signal.explanation}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Critical Issues */}
      {criticalFindings.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
            <span className="text-red-400">⚠</span>
            Critical Issues ({criticalFindings.length})
          </h4>
          <div className="space-y-2">
            {criticalFindings.map((finding, i) => (
              <div
                key={i}
                className="rounded border border-red-500/20 bg-red-500/5 p-3 text-sm"
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
                  <pre className="mt-2 rounded bg-black/30 p-2 text-xs overflow-x-auto">
                    <code>{finding.snippet}</code>
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bad Practices */}
      {nonCriticalFindings.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
            Bad Practices
            <span className="text-xs px-1.5 py-0.5 rounded-sm text-amber-400 bg-amber-400/10">
              {analysis.bad_practices.score}/100
            </span>
          </h4>
          <div className="space-y-2">
            {nonCriticalFindings.map((f, i) => (
              <div key={i} className="rounded border border-border p-2 text-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={cn(
                      "text-xs px-1 py-0.5 rounded-sm",
                      f.severity === "warning"
                        ? "text-amber-400 bg-amber-400/10"
                        : "text-muted-foreground bg-white/5"
                    )}
                  >
                    {f.severity}
                  </span>
                  <span className="font-medium">{f.type}</span>
                  <span className="text-muted-foreground ml-auto">
                    {f.file}:{f.line}
                  </span>
                </div>
                <p className="text-muted-foreground">{f.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Code Quality */}
      <div>
        <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
          Code Quality
          <span className="text-xs px-1.5 py-0.5 rounded-sm text-muted-foreground bg-white/5">
            {analysis.code_quality.score}/100
          </span>
        </h4>
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div>
            <p className="text-muted-foreground">Organization</p>
            <p className="font-medium">{analysis.code_quality.files_organized}%</p>
          </div>
          <div>
            <p className="text-muted-foreground">README</p>
            <p className="font-medium">{analysis.code_quality.readme_quality}%</p>
          </div>
          <div>
            <p className="text-muted-foreground">Dependencies</p>
            <p className="font-medium">{analysis.code_quality.dependency_health}%</p>
          </div>
        </div>
        {analysis.code_quality.findings.length > 0 && (
          <div className="mt-3 space-y-2">
            {analysis.code_quality.findings.map((f, i) => (
              <div key={i} className="rounded border border-border p-2 text-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs px-1 py-0.5 rounded-sm text-muted-foreground bg-white/5">
                    {f.severity}
                  </span>
                  <span className="font-medium">{f.type}</span>
                  <span className="text-muted-foreground ml-auto">
                    {f.file}:{f.line}
                  </span>
                </div>
                <p className="text-muted-foreground">{f.explanation}</p>
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
              className="flex items-center justify-between text-xs py-1 border-b border-border/50 last:border-0"
            >
              <span className="font-mono">{f.path}</span>
              <span className="text-muted-foreground">{f.loc} LOC</span>
            </div>
          ))}
        </div>
      </div>

      {/* Interview Questions */}
      {questions && questions.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
            Interview Questions
            <span className="text-xs px-1.5 py-0.5 rounded-sm text-muted-foreground bg-white/5">
              {questions.length}
            </span>
          </h4>
          <div className="space-y-2">
            {questions.map((q, i) => (
              <div key={i} className="rounded border border-border p-3">
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
                <span className="inline-block mt-2 text-xs px-1.5 py-0.5 rounded-sm text-muted-foreground bg-white/5">
                  {q.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Main Page
// =============================================================================

const DuoScanPage = () => {
  const [searchParams] = useSearchParams();
  const linkA = searchParams.get("linkA") ?? "";
  const linkB = searchParams.get("linkB") ?? "";

  const streamA = useAnalyzeStream();
  const streamB = useAnalyzeStream();

  const [compat, setCompat] = useState<CompatibilityResponse | null>(null);
  const [compatLoading, setCompatLoading] = useState(false);
  const [compatError, setCompatError] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const startedRef = useRef(false);

  // Start both streams on mount
  useEffect(() => {
    if (startedRef.current) return;
    if (!linkA || !linkB) return;
    startedRef.current = true;
    streamA.startStream(linkA);
    streamB.startStream(linkB);
  }, [linkA, linkB]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch compatibility when both done
  useEffect(() => {
    if (
      !streamA.isDone ||
      !streamB.isDone ||
      !streamA.analysis ||
      !streamB.analysis ||
      compat ||
      compatLoading
    ) {
      return;
    }

    setCompatLoading(true);
    fetchCompatibility(
      streamA.analysis,
      streamA.evaluation,
      streamB.analysis,
      streamB.evaluation
    )
      .then(setCompat)
      .catch((err) => setCompatError(err.message))
      .finally(() => setCompatLoading(false));
  }, [streamA.isDone, streamB.isDone]); // eslint-disable-line react-hooks/exhaustive-deps

  const bothDone = streamA.isDone && streamB.isDone;

  return (
    <GridBackground>
      <div
        className="flex flex-col min-h-screen"
        style={
          {
            "--primary": "var(--hacker)",
            "--primary-foreground": "var(--hacker-foreground)",
            "--ring": "var(--hacker)",
          } as React.CSSProperties
        }
      >
        <Header />

        <main className="container mx-auto px-4 py-8 space-y-12">
          {/* Section 1: Match Analysis Header */}
          <div className="text-center animate-fade-in-up">
            <h1
              className="text-2xl md:text-3xl font-bold uppercase tracking-widest"
              style={{ color: "hsl(var(--hacker))" }}
            >
              Match Analysis
            </h1>
            {!bothDone && (
              <p className="text-sm text-muted-foreground mt-2">
                Analyzing both repositories...
              </p>
            )}
          </div>

          {/* Section 2: Score + Avatars (show after compat loads) */}
          {bothDone && streamA.analysis && streamB.analysis && compat && (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-8 animate-fade-in-up">
              {/* Person A avatar */}
              <div className="flex flex-col items-center gap-2">
                <img
                  src={`https://github.com/${streamA.analysis.repo.owner}.png?size=80`}
                  alt={streamA.analysis.repo.owner}
                  className="w-20 h-20 rounded-full border-2"
                  style={{
                    borderColor: getTier(streamA.analysis, streamA.evaluation)
                      .color,
                  }}
                />
                <span
                  className="text-xs uppercase tracking-widest font-bold"
                  style={{
                    color: getTier(streamA.analysis, streamA.evaluation).color,
                  }}
                >
                  {getTier(streamA.analysis, streamA.evaluation).tier}
                </span>
              </div>

              {/* Score */}
              <div className="text-center">
                <span
                  className="text-6xl font-bold font-mono"
                  style={{
                    color:
                      compat.score >= 80
                        ? "#22c55e"
                        : compat.score >= 60
                          ? "#06b6d4"
                          : compat.score >= 40
                            ? "#f59e0b"
                            : "#ef4444",
                  }}
                >
                  {compat.score}
                  <span className="text-2xl">%</span>
                </span>
                <p className="text-xs text-muted-foreground uppercase tracking-widest mt-1">
                  Compatibility Score
                </p>
              </div>

              {/* Person B avatar */}
              <div className="flex flex-col items-center gap-2">
                <img
                  src={`https://github.com/${streamB.analysis.repo.owner}.png?size=80`}
                  alt={streamB.analysis.repo.owner}
                  className="w-20 h-20 rounded-full border-2"
                  style={{
                    borderColor: getTier(streamB.analysis, streamB.evaluation)
                      .color,
                  }}
                />
                <span
                  className="text-xs uppercase tracking-widest font-bold"
                  style={{
                    color: getTier(streamB.analysis, streamB.evaluation).color,
                  }}
                >
                  {getTier(streamB.analysis, streamB.evaluation).tier}
                </span>
              </div>
            </div>
          )}

          {/* Section 3: Profile summaries side by side */}
          {bothDone && streamA.analysis && streamB.analysis && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 max-w-3xl mx-auto animate-fade-in-up">
              <ProfileSummary
                label="Person A"
                analysis={streamA.analysis}
                evaluation={streamA.evaluation}
              />
              <ProfileSummary
                label="Person B"
                analysis={streamB.analysis}
                evaluation={streamB.evaluation}
              />
            </div>
          )}

          {/* Section 4: Compatibility block */}
          {compat && <CompatibilityBlock compat={compat} />}
          {compatLoading && (
            <div className="flex justify-center py-8">
              <BarLoader />
            </div>
          )}
          {compatError && (
            <p className="text-center text-sm text-red-400">{compatError}</p>
          )}

          {/* Section 5: Rank Cards */}
          <div className="flex flex-col sm:flex-row items-center sm:items-start justify-center gap-6 flex-wrap">
            {streamA.analysis ? (
              <RankCard
                analysis={streamA.analysis}
                evaluation={streamA.evaluation}
                label="Person A"
              />
            ) : streamA.error ? (
              <ErrorCard label="Person A" error={streamA.error} />
            ) : (
              <LoadingCard label="Person A" />
            )}

            {streamB.analysis ? (
              <RankCard
                analysis={streamB.analysis}
                evaluation={streamB.evaluation}
                label="Person B"
              />
            ) : streamB.error ? (
              <ErrorCard label="Person B" error={streamB.error} />
            ) : (
              <LoadingCard label="Person B" />
            )}
          </div>

          {/* Section 6: View Evidence (expandable deep dive) */}
          {bothDone && streamA.analysis && streamB.analysis && (
            <div className="w-full max-w-5xl mx-auto animate-fade-in-up">
              <button
                onClick={() => setEvidenceOpen(!evidenceOpen)}
                className="flex items-center gap-2 mx-auto text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <ChevronDown
                  className={cn(
                    "h-4 w-4 transition-transform duration-200",
                    evidenceOpen && "rotate-180"
                  )}
                />
                <span className="uppercase tracking-widest text-xs font-medium">
                  View Evidence
                </span>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 transition-transform duration-200",
                    evidenceOpen && "rotate-180"
                  )}
                />
              </button>
              {evidenceOpen && (
                <div className="mt-6 flex flex-col md:flex-row gap-8 border border-border/50 rounded p-6">
                  <div className="flex-1 min-w-0">
                    <EvidencePanel
                      label="Person A"
                      analysis={streamA.analysis}
                      evaluation={streamA.evaluation}
                      questions={streamA.questions}
                    />
                  </div>
                  <div className="hidden md:block border-l border-border/50" />
                  <div className="block md:hidden border-t border-border/50" />
                  <div className="flex-1 min-w-0">
                    <EvidencePanel
                      label="Person B"
                      analysis={streamB.analysis}
                      evaluation={streamB.evaluation}
                      questions={streamB.questions}
                    />
                  </div>
                </div>
              )}
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

export default DuoScanPage;
