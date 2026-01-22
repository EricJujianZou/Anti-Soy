import { cn } from "@/lib/utils";

interface ScoreDisplayProps {
  label: string;
  value: number | string;
  maxValue?: number;
  suffix?: string;
  size?: "sm" | "lg";
}

export const ScoreDisplay = ({ 
  label, 
  value, 
  maxValue = 100,
  suffix = "",
  size = "lg"
}: ScoreDisplayProps) => {
  const isNumeric = typeof value === "number";
  const percentage = isNumeric ? (value / maxValue) * 100 : 0;

  return (
    <div className="relative border border-border bg-card/50 backdrop-blur-sm p-4">
      {/* Corner decorations */}
      <span className="absolute -top-px -left-px text-primary text-xs">┌</span>
      <span className="absolute -top-px -right-px text-primary text-xs">┐</span>
      <span className="absolute -bottom-px -left-px text-primary text-xs">└</span>
      <span className="absolute -bottom-px -right-px text-primary text-xs">┘</span>
      
      <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
        {label}
      </div>
      
      <div className={cn(
        "font-bold tabular-nums text-primary",
        size === "lg" ? "text-4xl" : "text-2xl"
      )}>
        {value}{isNumeric ? suffix : ""}
      </div>
      
      {/* Progress bar */}
      {isNumeric && (
        <div className="mt-3 h-1 bg-muted rounded-sm overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}
    </div>
  );
};
