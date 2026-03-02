import { cn } from "@/utils/utils";
import { ReactNode } from "react";

interface GridBackgroundProps {
  children: ReactNode;
  className?: string;
}

export const GridBackground = ({ children, className }: GridBackgroundProps) => {
  return (
    <div className={cn("relative min-h-screen bg-background overflow-hidden", className)}>
      {/* Scanline overlay */}
      <div 
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            hsl(var(--foreground) / 0.015) 2px,
            hsl(var(--foreground) / 0.015) 4px
          )`,
        }}
      />
      
      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
};
