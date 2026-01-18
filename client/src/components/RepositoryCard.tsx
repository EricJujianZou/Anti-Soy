import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";

export interface Repository {
  id: string;
  name: string;
  description: string;
  language: string;
  languageColor: string;
  stars: number;
  forks: number;
  lastUpdated: string;
  isPrivate: boolean;
}

interface RepositoryCardProps {
  repository: Repository;
  className?: string;
  index?: number;
}

export const RepositoryCard = ({ repository, className, index = 0 }: RepositoryCardProps) => {
  return (
    <Link
      to={`/repo/${repository.id}`}
      className={cn(
        "block relative border border-border bg-card/50 backdrop-blur-sm",
        "hover:border-primary/50 hover:glow-amber transition-all duration-300",
        "group cursor-pointer",
        className
      )}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Corner decorations */}
      <span className="absolute -top-px -left-px text-primary text-xs opacity-50 group-hover:opacity-100 transition-opacity">┌</span>
      <span className="absolute -top-px -right-px text-primary text-xs opacity-50 group-hover:opacity-100 transition-opacity">┐</span>
      <span className="absolute -bottom-px -left-px text-primary text-xs opacity-50 group-hover:opacity-100 transition-opacity">└</span>
      <span className="absolute -bottom-px -right-px text-primary text-xs opacity-50 group-hover:opacity-100 transition-opacity">┘</span>

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-primary text-sm">▸</span>
            <h3 className="text-foreground font-medium group-hover:text-primary transition-colors">
              {repository.name}
            </h3>
            {repository.isPrivate && (
              <span className="text-[10px] px-1.5 py-0.5 border border-muted text-muted-foreground uppercase tracking-wider">
                Private
              </span>
            )}
          </div>
          <span className="text-xs text-muted-foreground">
            {repository.lastUpdated}
          </span>
        </div>

        {/* Description */}
        <p className="text-sm text-muted-foreground mb-4 line-clamp-2 min-h-[40px]">
          {repository.description || "No description provided"}
        </p>

        {/* Footer */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            {/* Language */}
            <div className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: repository.languageColor }}
              />
              <span className="text-foreground">{repository.language}</span>
            </div>

            {/* Stars */}
            <div className="flex items-center gap-1 text-muted-foreground">
              <span>★</span>
              <span>{repository.stars.toLocaleString()}</span>
            </div>

            {/* Forks */}
            <div className="flex items-center gap-1 text-muted-foreground">
              <span>⑂</span>
              <span>{repository.forks.toLocaleString()}</span>
            </div>
          </div>

          <span className="text-primary opacity-0 group-hover:opacity-100 transition-opacity">
            View Analysis →
          </span>
        </div>
      </div>
    </Link>
  );
};
