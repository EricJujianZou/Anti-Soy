import { useParams, useNavigate } from "react-router-dom";
import { Header } from "@/components/Header";
import { useBatchStatus } from "@/hooks/useBatchStatus";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/utils";
import { Loader2, CheckCircle2, XCircle, ExternalLink, Building2 } from "lucide-react";
import type { BatchItemStatus } from "@/services/batchApi";

const VerdictBadge = ({ verdict }: { verdict: string | null | undefined }) => {
  if (!verdict) return null;

  const verdictLower = verdict.toLowerCase();
  let colorClass = "bg-muted text-muted-foreground border-muted-foreground/20";
  
  if (verdictLower.includes("slop")) {
    colorClass = "bg-destructive/10 text-destructive border-destructive/20";
  } else if (verdictLower.includes("junior")) {
    colorClass = "bg-amber-500/10 text-amber-500 border-amber-500/20";
  } else if (verdictLower.includes("senior")) {
    colorClass = "bg-green-500/10 text-green-500 border-green-500/20";
  } else if (verdictLower.includes("ai coder") || verdictLower.includes("good ai")) {
    colorClass = "bg-blue-500/10 text-blue-500 border-blue-500/20";
  }

  return (
    <Badge variant="outline" className={cn("uppercase tracking-widest text-[10px] font-bold px-2 py-0.5", colorClass)}>
      {verdict}
    </Badge>
  );
};

const CandidateCard = ({ item, batchPriorities }: { item: BatchItemStatus, batchPriorities?: string[] }) => {
  const navigate = useNavigate();
  const isCompleted = item.status === "completed";
  const isError = item.status === "error";
  const isPending = item.status === "pending" || item.status === "running";

  const handleClick = () => {
    if (isCompleted && item.repo_id) {
      const searchParams = new URLSearchParams();
      if (item.repo_url) {
        searchParams.append("link", item.repo_url);
      }
      if (batchPriorities && batchPriorities.length > 0) {
        searchParams.append("priorities", batchPriorities.join(","));
      }
      navigate(`/repo/${item.repo_id}?${searchParams.toString()}`);
    }
  };

  return (
    <Card 
      className={cn(
        "border-border bg-card/50 backdrop-blur-sm relative overflow-hidden transition-all duration-300",
        isCompleted ? "hover:border-primary/50 hover:glow-amber cursor-pointer hover:-translate-y-1" : "cursor-default",
        isError ? "border-destructive/30" : ""
      )}
      onClick={handleClick}
    >
      {/* Corner decorations for completed items */}
      {isCompleted && (
        <>
          <span className="absolute -top-px -left-px text-primary/30 text-xs p-0.5">┌</span>
          <span className="absolute -top-px -right-px text-primary/30 text-xs p-0.5">┐</span>
          <span className="absolute -bottom-px -left-px text-primary/30 text-xs p-0.5">└</span>
          <span className="absolute -bottom-px -right-px text-primary/30 text-xs p-0.5">┘</span>
        </>
      )}

      <CardContent className="p-5">
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center gap-2">
            {isPending && <Loader2 className="w-4 h-4 text-primary animate-spin" />}
            {isCompleted && <CheckCircle2 className="w-4 h-4 text-green-500" />}
            {isError && <XCircle className="w-4 h-4 text-destructive" />}
            
            <span className={cn(
              "text-[10px] uppercase tracking-widest font-bold",
              isPending ? "text-primary" : "",
              isCompleted ? "text-green-500" : "",
              isError ? "text-destructive" : ""
            )}>
              {item.status === "running" ? "Analyzing..." : item.status}
            </span>
          </div>
          
          {isCompleted && <VerdictBadge verdict={item.verdict} />}
          {isError && <Badge variant="outline" className="bg-destructive/10 text-destructive border-destructive/20 uppercase tracking-widest text-[10px] font-bold">Unresolvable</Badge>}
        </div>

        <div className="space-y-3">
          <div>
            <h3 className="text-lg font-bold text-foreground truncate">
              {item.candidate_name || item.filename}
            </h3>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
              <Building2 className="w-3 h-3" />
              <span>{isError ? "—" : "University not extracted"}</span>
            </div>
          </div>

          <div className="pt-2 border-t border-border/50">
            <p className="text-xs text-muted-foreground italic line-clamp-2 min-h-[2.5rem]">
              {isCompleted ? (
                item.standout_features && item.standout_features.length > 0 
                  ? item.standout_features[0] 
                  : "Nothing particularly stands out about this project"
              ) : isError ? (
                item.error_message || "Could not resolve GitHub repository from resume"
              ) : (
                "Processing candidate profile..."
              )}
            </p>
          </div>
          
          {isCompleted && (
            <div className="pt-2 flex justify-end">
              <span className="text-[10px] uppercase tracking-widest font-bold text-primary flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                View Report <ExternalLink className="w-3 h-3" />
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

const BatchDashboard = () => {
  const { batchId } = useParams<{ batchId: string }>();
  const { data, isLoading, error } = useBatchStatus(batchId || "");
  const navigate = useNavigate();

  // Get priorities from response or fallback to localStorage
  const priorities = data?.priorities || (() => {
    try {
      const stored = localStorage.getItem(`antisoy_batch_${batchId}_priorities`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  })();

  if (error) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container mx-auto px-4 py-20 text-center">
          <XCircle className="w-16 h-16 text-destructive mx-auto mb-4" />
          <h1 className="text-2xl font-bold mb-2 uppercase tracking-widest">Error</h1>
          <p className="text-muted-foreground mb-8">{error}</p>
          <button 
            onClick={() => navigate("/upload")}
            className="border border-primary text-primary px-8 py-2 uppercase tracking-widest text-sm font-bold hover:bg-primary/10 transition-colors"
          >
            Back to Upload
          </button>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-4 py-12">
        <div className="mb-10">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-4">
            <div>
              <h1 className="text-3xl font-bold text-foreground uppercase tracking-widest">
                Candidate Batch Analysis
              </h1>
              <p className="text-muted-foreground mt-1">
                {isLoading ? (
                  "Loading batch data..."
                ) : (
                  `${data?.completed_items || 0} of ${data?.total_items || 0} complete`
                )}
              </p>
            </div>
            
            {!isLoading && data?.status !== "completed" && data?.status !== "failed" && (
              <div className="flex items-center gap-2 text-primary bg-primary/5 px-3 py-1.5 rounded-full border border-primary/20 animate-pulse">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-xs font-bold uppercase tracking-widest">Live Polling Active</span>
              </div>
            )}
          </div>
          
          {/* Progress bar */}
          {!isLoading && (
            <div className="w-full h-1 bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-primary transition-all duration-500 ease-out"
                style={{ width: `${((data?.completed_items || 0) / (data?.total_items || 1)) * 100}%` }}
              />
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-48 rounded-lg border border-border bg-card/20 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data?.items.map((item) => (
              <CandidateCard key={item.item_id} item={item} batchPriorities={priorities} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default BatchDashboard;
