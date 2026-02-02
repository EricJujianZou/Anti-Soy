import { cn } from "@/utils/utils";
import { useNavigate } from "react-router-dom";

interface HeaderProps {
  className?: string;
}

export const Header = ({ className }: HeaderProps) => {
  const navigate = useNavigate();

  return (
    <header className={cn(
      "border-b border-border bg-card/30 backdrop-blur-md",
      className
    )}>
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="flex items-center gap-2 text-primary font-bold text-xl tracking-tight hover:text-primary/80 transition-colors"
              aria-label="Go back"
            >
              <img
                src="/logo.png"
                alt="ANTI-SOY logo"
                className="h-16 w-16"
              />
              ANTI-SOY
            </button>
            <div className="hidden sm:flex items-center gap-1 text-xs text-muted-foreground">
              <span className="text-primary">●</span>
              <span>v1.0.0</span>
            </div>
          </div>
          
          <span className="text-xs text-muted-foreground uppercase tracking-widest">
            GitHub Profile Analyzer
          </span>
        </div>
      </div>
    </header>
  );
};
