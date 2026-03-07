import { cn } from "@/utils/utils";
import { getTier, deriveTraits, type TierResult } from "@/utils/rankTier";
import type { AnalysisResponse, EvaluationEvent } from "@/services/api";

interface RankCardProps {
  analysis: AnalysisResponse;
  evaluation: EvaluationEvent | null;
  label?: "Person A" | "Person B";
}

function LanguageBar({ languages }: { languages: Record<string, number> }) {
  const sorted = Object.entries(languages)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3);
  const total = sorted.reduce((s, [, v]) => s + v, 0) || 1;

  const colors = ["#06b6d4", "#a855f7", "#f59e0b"];

  return (
    <div className="space-y-1.5">
      <div className="flex h-2 w-full overflow-hidden rounded-sm bg-white/5">
        {sorted.map(([lang, bytes], i) => (
          <div
            key={lang}
            style={{
              width: `${(bytes / total) * 100}%`,
              backgroundColor: colors[i % colors.length],
            }}
          />
        ))}
      </div>
      <div className="flex gap-2 flex-wrap">
        {sorted.map(([lang], i) => (
          <span
            key={lang}
            className="text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded-sm"
            style={{
              color: colors[i % colors.length],
              backgroundColor: `${colors[i % colors.length]}15`,
            }}
          >
            {lang}
          </span>
        ))}
      </div>
    </div>
  );
}

function ScoreChip({
  label,
  value,
  invert,
}: {
  label: string;
  value: number;
  invert?: boolean;
}) {
  const isGood = invert ? value <= 30 : value >= 70;
  const isBad = invert ? value >= 60 : value <= 30;

  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
        {label}
      </span>
      <span
        className={cn(
          "text-sm font-bold font-mono",
          isGood && "text-green-400",
          isBad && "text-red-400",
          !isGood && !isBad && "text-amber-400"
        )}
      >
        {value}%
      </span>
    </div>
  );
}

export function RankCard({ analysis, evaluation, label }: RankCardProps) {
  const tier: TierResult = getTier(analysis, evaluation);
  const traits = deriveTraits(analysis, evaluation);
  const owner = analysis.repo.owner;
  const repoName = analysis.repo.name;
  const avatarUrl = `https://github.com/${owner}.png?size=80`;

  return (
    <div
      className="relative w-[380px] bg-[hsl(30,10%,8%)] border p-5 space-y-4 shrink-0"
      style={{ borderColor: tier.color }}
    >
      {/* Corner decorations */}
      <span
        className="absolute -top-px -left-px text-sm"
        style={{ color: tier.color }}
      >
        ┌
      </span>
      <span
        className="absolute -top-px -right-px text-sm"
        style={{ color: tier.color }}
      >
        ┐
      </span>
      <span
        className="absolute -bottom-px -left-px text-sm"
        style={{ color: tier.color }}
      >
        └
      </span>
      <span
        className="absolute -bottom-px -right-px text-sm"
        style={{ color: tier.color }}
      >
        ┘
      </span>

      {/* Label (duo mode) */}
      {label && (
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
          {label}
        </span>
      )}

      {/* Header: avatar + name + tier badge */}
      <div className="flex items-center gap-3">
        <img
          src={avatarUrl}
          alt={owner}
          className="w-12 h-12 rounded-full border-2"
          style={{ borderColor: tier.color }}
        />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-foreground truncate">
            {owner}/{repoName}
          </div>
          <span
            className="inline-block text-[10px] uppercase tracking-widest font-bold px-2 py-0.5 mt-1 rounded-sm"
            style={{
              color: tier.color,
              backgroundColor: `${tier.color}20`,
              border: `1px solid ${tier.color}40`,
            }}
          >
            {tier.tier}
          </span>
        </div>
      </div>

      {/* Tier description */}
      <p className="text-xs text-muted-foreground italic">{tier.description}</p>

      {/* Language bar */}
      <LanguageBar languages={analysis.repo.languages} />

      {/* Traits */}
      {traits.length > 0 && (
        <div className="space-y-1">
          {traits.map((trait, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span style={{ color: tier.color }}>■</span>
              <span className="text-foreground/80">{trait}</span>
            </div>
          ))}
        </div>
      )}

      {/* Score chips */}
      <div className="flex justify-between pt-2 border-t border-border/50">
        <ScoreChip label="AI Usage" value={analysis.ai_slop.score} invert />
        <ScoreChip label="Code Quality" value={analysis.code_quality.score} />
        <ScoreChip
          label="Bad Practices"
          value={analysis.bad_practices.score}
          invert
        />
      </div>
    </div>
  );
}
