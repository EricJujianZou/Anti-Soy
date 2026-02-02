import { cn } from "@/utils/utils";

interface Language {
  name: string;
  percentage: number;
}

interface LanguagesDisplayProps {
  languages: Language[];
  className?: string;
}

export const LanguagesDisplay = ({ languages, className }: LanguagesDisplayProps) => {
  // Generate yellow/amber shades for the bar segments
  const getBarColor = (index: number): string => {
    const shades = [
      "hsl(var(--primary))",
      "hsl(var(--primary) / 0.8)",
      "hsl(var(--primary) / 0.6)",
      "hsl(var(--primary) / 0.4)",
      "hsl(var(--primary) / 0.3)",
    ];
    return shades[Math.min(index, shades.length - 1)];
  };

  return (
    <div className={cn(
      "relative border border-border bg-card/50 backdrop-blur-sm p-4",
      className
    )}>
      {/* Corner decorations */}
      <span className="absolute -top-px -left-px text-primary text-xs">┌</span>
      <span className="absolute -top-px -right-px text-primary text-xs">┐</span>
      <span className="absolute -bottom-px -left-px text-primary text-xs">└</span>
      <span className="absolute -bottom-px -right-px text-primary text-xs">┘</span>
      
      <div className="flex items-center gap-2 mb-4 pb-2 border-b border-border">
        <span className="text-primary">■</span>
        <span className="text-xs uppercase tracking-widest text-muted-foreground">
          Languages
        </span>
      </div>
      
      {/* Stacked bar */}
      <div className="h-3 flex rounded-sm overflow-hidden mb-6">
        {languages.map((lang, index) => (
          <div
            key={lang.name}
            style={{
              width: `${lang.percentage}%`,
              backgroundColor: getBarColor(index),
            }}
          />
        ))}
      </div>
      
      {/* Language labels */}
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {languages.map((lang, index) => (
          <div key={lang.name} className="flex items-center gap-2">
            <span
              className={cn(
                "glyph-spinner text-sm leading-none",
                index % 2 === 0 ? "text-primary" : "text-foreground"
              )}
              aria-hidden="true"
            />
            <span className="text-xs uppercase tracking-wider text-muted-foreground">
              {lang.name}
            </span>
            <span className="text-xs text-foreground/70">
              {lang.percentage.toFixed(2)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
