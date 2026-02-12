import { useState, useRef } from "react";
import { cn } from "@/utils/utils";

interface Example {
  label: string;
  url: string;
}

interface TerminalInputProps {
  onSubmit: (value: string) => void;
  placeholder?: string;
  isLoading?: boolean;
  examples?: Example[];
}

export const TerminalInput = ({
  onSubmit,
  placeholder = "github_repository_url",
  isLoading = false,
  examples,
}: TerminalInputProps) => {
  const [value, setValue] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !isLoading) {
      onSubmit(value.trim());
    }
  };

  const handleRunExample = (url: string) => {
    if (isLoading) return;
    setValue(url);
    inputRef.current?.focus();
    setTimeout(() => {
      onSubmit(url);
    }, 600);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
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
            ref={inputRef}
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

      {examples && examples.length > 0 && (
        <>
          <div className="flex items-center gap-3 mt-4">
            <div className="flex-1 border-t border-border/50" />
            <span className="text-xs text-muted-foreground uppercase tracking-widest">or choose an example</span>
            <div className="flex-1 border-t border-border/50" />
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2">
            {examples.map((example) => (
              <button
                key={example.url}
                type="button"
                onClick={() => handleRunExample(example.url)}
                disabled={isLoading}
                className={cn(
                  "border border-primary/50 bg-transparent text-primary/80 py-2 px-3",
                  "uppercase tracking-widest text-[10px] font-medium",
                  "transition-all duration-300",
                  "hover:border-primary hover:text-primary hover:bg-primary/5",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "relative group"
                )}
              >
                <span className="absolute -top-px -left-px text-primary/50 group-hover:text-primary text-xs">┌</span>
                <span className="absolute -top-px -right-px text-primary/50 group-hover:text-primary text-xs">┐</span>
                <span className="absolute -bottom-px -left-px text-primary/50 group-hover:text-primary text-xs">└</span>
                <span className="absolute -bottom-px -right-px text-primary/50 group-hover:text-primary text-xs">┘</span>
                [ {example.label} ]
              </button>
            ))}
          </div>
        </>
      )}
    </form>
  );
};
