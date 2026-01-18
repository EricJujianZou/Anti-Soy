import { useState } from "react";
import { cn } from "@/lib/utils";

interface TerminalInputProps {
  onSubmit: (value: string) => void;
  placeholder?: string;
  isLoading?: boolean;
}

export const TerminalInput = ({ 
  onSubmit, 
  placeholder = "github_username",
  isLoading = false 
}: TerminalInputProps) => {
  const [value, setValue] = useState("");
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !isLoading) {
      onSubmit(value.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <div className={cn(
        "relative border bg-card/80 backdrop-blur-sm transition-all duration-300",
        isFocused ? "border-primary glow-amber" : "border-border",
        isLoading && "opacity-70"
      )}>
        {/* Corner decorations */}
        <span className="absolute -top-px -left-px text-primary text-sm">┌</span>
        <span className="absolute -top-px -right-px text-primary text-sm">┐</span>
        <span className="absolute -bottom-px -left-px text-primary text-sm">└</span>
        <span className="absolute -bottom-px -right-px text-primary text-sm">┘</span>
        
        <div className="flex items-center gap-2 p-4">
          <span className="text-primary font-medium">&gt;</span>
          <span className="text-muted-foreground">analyze</span>
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder}
            disabled={isLoading}
            className="flex-1 bg-transparent border-none outline-none text-foreground placeholder:text-muted-foreground/50 font-mono"
          />
          <span className={cn(
            "w-2 h-5 bg-primary",
            isFocused && "cursor-blink"
          )} />
        </div>
      </div>
      
      <button
        type="submit"
        disabled={!value.trim() || isLoading}
        className={cn(
          "mt-4 w-full border border-primary bg-primary/10 text-primary py-3 px-6",
          "uppercase tracking-widest text-sm font-medium",
          "transition-all duration-300",
          "hover:bg-primary hover:text-primary-foreground",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          "relative group"
        )}
      >
        <span className="absolute -top-px -left-px text-primary group-hover:text-primary-foreground text-xs">┌</span>
        <span className="absolute -top-px -right-px text-primary group-hover:text-primary-foreground text-xs">┐</span>
        <span className="absolute -bottom-px -left-px text-primary group-hover:text-primary-foreground text-xs">└</span>
        <span className="absolute -bottom-px -right-px text-primary group-hover:text-primary-foreground text-xs">┘</span>
        
        {isLoading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="pulse-glow">●</span>
            Processing...
          </span>
        ) : (
          "[ run scan ]"
        )}
      </button>
    </form>
  );
};
