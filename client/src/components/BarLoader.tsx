import { cn } from "@/lib/utils";

interface BarLoaderProps {
  className?: string;
}

export const BarLoader = ({ className }: BarLoaderProps) => {
  const bars = "▁▃▅▇█▇▅▃".split("");
  
  return (
    <div className={cn("flex items-end justify-center gap-0.5 text-primary text-5xl", className)}>
      {bars.map((bar, index) => (
        <span 
          key={index}
          className="animate-bar-wave"
          style={{ 
            animationDelay: `${index * 0.1}s`,
          }}
        >
          {bar}
        </span>
      ))}
    </div>
  );
};
