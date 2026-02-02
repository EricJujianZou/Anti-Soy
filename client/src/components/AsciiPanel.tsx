import { cn } from "@/utils/utils";
import { ReactNode } from "react";

interface AsciiPanelProps {
  children: ReactNode;
  title?: string;
  className?: string;
  variant?: "default" | "highlight" | "muted";
}

export const AsciiPanel = ({ 
  children, 
  title, 
  className,
  variant = "default" 
}: AsciiPanelProps) => {
  const variants = {
    default: "border-border",
    highlight: "border-primary/50 glow-amber",
    muted: "border-muted",
  };

  return (
    <div className={cn(
      "relative border bg-card/50 backdrop-blur-sm",
      variants[variant],
      className
    )}>
      {/* Corner decorations */}
      <span className="absolute -top-px -left-px text-primary text-xs">┌</span>
      <span className="absolute -top-px -right-px text-primary text-xs">┐</span>
      <span className="absolute -bottom-px -left-px text-primary text-xs">└</span>
      <span className="absolute -bottom-px -right-px text-primary text-xs">┘</span>
      
      {title && (
        <div className="absolute -top-3 left-4 px-2 bg-background">
          <span className="text-xs text-muted-foreground uppercase tracking-widest">
            {title}
          </span>
        </div>
      )}
      
      <div className="p-4">
        {children}
      </div>
    </div>
  );
};
