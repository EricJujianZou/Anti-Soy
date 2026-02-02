import { cn } from "@/utils/utils";
import { ReactNode } from "react";

interface GridBackgroundProps {
  children: ReactNode;
  className?: string;
}

export const GridBackground = ({ children, className }: GridBackgroundProps) => {
  return (
    <div className={cn("relative min-h-screen bg-background overflow-hidden", className)}>
      {/* Animated Grid pattern */}
      <div 
        className="absolute inset-0 opacity-30 animate-grid-move"
        style={{
          backgroundImage: `
            linear-gradient(hsl(var(--border) / 0.3) 1px, transparent 1px),
            linear-gradient(90deg, hsl(var(--border) / 0.3) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px',
        }}
      />
      
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
      
      {/* Radial gradient overlay */}
      <div 
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(
            ellipse at 50% 0%,
            hsl(var(--primary) / 0.08) 0%,
            transparent 50%
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
