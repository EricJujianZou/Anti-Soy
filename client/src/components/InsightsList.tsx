import { cn } from "@/utils/utils";
import { AlertTriangle, Check, Lightbulb } from "lucide-react";

export interface Insight {
  id: string;
  type: "strength" | "red-flag" | "hint";
  text: string;
}

interface InsightsListProps {
  title: string;
  insights: Insight[];
  className?: string;
}

export const InsightsList = ({ title, insights, className }: InsightsListProps) => {
  const getIcon = (type: Insight["type"]) => {
    switch (type) {
      case "strength":
        return <Check className="w-4 h-4 text-primary flex-shrink-0" />;
      case "red-flag":
        return <AlertTriangle className="w-4 h-4 text-primary flex-shrink-0" />;
      case "hint":
        return <Lightbulb className="w-4 h-4 text-primary flex-shrink-0" />;
    }
  };

  return (
    <div className={cn(
      "relative border border-border bg-card/50 backdrop-blur-sm",
      className
    )}>
      {/* Corner decorations */}
      <span className="absolute -top-px -left-px text-primary text-xs">┌</span>
      <span className="absolute -top-px -right-px text-primary text-xs">┐</span>
      <span className="absolute -bottom-px -left-px text-primary text-xs">└</span>
      <span className="absolute -bottom-px -right-px text-primary text-xs">┘</span>
      
      <div className="p-4">
        <div className="flex items-center gap-2 mb-4 pb-2 border-b border-border">
          <span className="text-primary">■</span>
          <span className="text-xs uppercase tracking-widest text-muted-foreground">
            {title}
          </span>
        </div>
        
        <div className="space-y-3">
          {insights.map((insight, index) => (
            <div 
              key={insight.id}
              className="flex items-start gap-3 animate-fade-in-up"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              {getIcon(insight.type)}
              <span className="text-sm text-foreground/90 leading-relaxed">
                {insight.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
