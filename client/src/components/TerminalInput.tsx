import { useState, useRef } from "react";
import { cn } from "@/utils/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { PRIORITY_OPTIONS, type PriorityKey } from "@/services/api";

interface Example {
  label: string;
  url: string;
}

interface TerminalInputProps {
  onSubmit: (value: string, priorities: PriorityKey[]) => void;
  placeholder?: string;
  isLoading?: boolean;
  examples?: Example[];
  secondaryAction?: React.ReactNode;
  onSecondaryAction?: (priorities: PriorityKey[]) => void;
  hidePriorities?: boolean;
  submitLabel?: string;
}

export const TerminalInput = ({
  onSubmit,
  placeholder = "github_repository_url",
  isLoading = false,
  examples,
  secondaryAction,
  onSecondaryAction,
  hidePriorities = false,
  submitLabel,
}: TerminalInputProps) => {
  const [value, setValue] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [priorities, setPriorities] = useState<Set<PriorityKey>>(
    new Set(PRIORITY_OPTIONS.map((o) => o.key))
  );

  const togglePriority = (key: PriorityKey) => {
    setPriorities((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size <= 1) return prev; // minimum 1
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const prioritiesArray = () => Array.from(priorities);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !isLoading) {
      onSubmit(value.trim(), prioritiesArray());
    }
  };

  const handleRunExample = (url: string) => {
    if (isLoading) return;
    setValue(url);
    inputRef.current?.focus();
    setTimeout(() => {
      onSubmit(url, prioritiesArray());
    }, 600);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl">
      {/* Upload Resumes — prominent CTA */}
      {(secondaryAction || onSecondaryAction) && (
        <div className="mb-6">
          {onSecondaryAction ? (
            <div className="flex flex-col items-center">
              <button
                type="button"
                onClick={() => onSecondaryAction(prioritiesArray())}
                className={cn(
                  "border border-primary bg-primary/10 text-primary py-2.5 px-8",
                  "uppercase tracking-widest text-xs font-medium",
                  "transition-all duration-300",
                  "hover:bg-primary hover:text-primary-foreground",
                  "relative group"
                )}
              >
                <span className="absolute -top-px -left-px text-primary group-hover:text-primary-foreground text-xs">┌</span>
                <span className="absolute -top-px -right-px text-primary group-hover:text-primary-foreground text-xs">┐</span>
                <span className="absolute -bottom-px -left-px text-primary group-hover:text-primary-foreground text-xs">└</span>
                <span className="absolute -bottom-px -right-px text-primary group-hover:text-primary-foreground text-xs">┘</span>
                [ upload candidate resumes ]
              </button>
              <p className="text-[10px] text-muted-foreground mt-1.5 tracking-wider">
                Batch analyze up to 10 resumes at once
              </p>
            </div>
          ) : (
            secondaryAction
          )}

          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 border-t border-border/50" />
            <span className="text-xs text-muted-foreground uppercase tracking-widest">or paste a github url</span>
            <div className="flex-1 border-t border-border/50" />
          </div>
        </div>
      )}

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

      {/* Evaluation Priorities */}
      {!hidePriorities && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
          <span className="text-xs text-muted-foreground uppercase tracking-widest mr-1">Priorities:</span>
          {PRIORITY_OPTIONS.map((opt) => (
            <label
              key={opt.key}
              className="flex items-center gap-1.5 cursor-pointer select-none group"
            >
              <Checkbox
                checked={priorities.has(opt.key)}
                onCheckedChange={() => togglePriority(opt.key)}
                disabled={isLoading}
                className="border-primary/60 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
              />
              <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                {opt.label}
              </span>
            </label>
          ))}
        </div>
      )}

      <div className="flex justify-center mt-4">
        <button
          type="submit"
          disabled={!value.trim() || isLoading}
          className={cn(
            "w-3/5 border border-primary bg-primary/10 text-primary py-2.5 px-6",
            "uppercase tracking-widest text-xs font-medium",
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
            submitLabel ?? "[ run scan ]"
          )}
        </button>
      </div>

      {examples && examples.length > 0 && (
        <>
          <div className="flex items-center gap-3 mt-4 max-w-sm mx-auto">
            <div className="flex-1 border-t border-border/50" />
            <span className="text-xs text-muted-foreground uppercase tracking-widest">or choose an example</span>
            <div className="flex-1 border-t border-border/50" />
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2 max-w-sm mx-auto">
            {examples.map((example) => (
              <button
                key={example.url}
                type="button"
                onClick={() => handleRunExample(example.url)}
                disabled={isLoading}
                className={cn(
                  "border border-primary/50 bg-transparent text-primary/80 py-1.5 px-2",
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
