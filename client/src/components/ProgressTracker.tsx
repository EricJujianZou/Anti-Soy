import { cn } from "@/utils/utils";
import { BarLoader } from "./BarLoader";

export type StepStatus = "pending" | "active" | "complete";

export interface PipelineStep {
  id: string;
  label: string;
  description: string;
  status: StepStatus;
}

interface ProgressTrackerProps {
  steps?: PipelineStep[];
  className?: string;
}

export const ProgressTracker = ({ className }: ProgressTrackerProps) => {
  return (
    <div className={cn("flex items-center justify-center py-12", className)}>
      <BarLoader />
    </div>
  );
};
