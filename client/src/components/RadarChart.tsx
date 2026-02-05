import { cn } from "@/utils/utils";

interface RadarDataPoint {
  label: string;
  value: number;
  maxValue?: number;
}

interface RadarChartProps {
  data: RadarDataPoint[];
  className?: string;
}

export const RadarChart = ({ data, className }: RadarChartProps) => {
  const sizeX = 250;
  const sizeY = 220;
  const centerX = sizeX / 2;
  const centerY = sizeY / 2;
  const maxRadius = ((sizeX < sizeY) ? sizeX : sizeY) / 2 - 40;
  const levels = 4;

  const angleStep = (2 * Math.PI) / data.length;
  const startAngle = -Math.PI / 2; // Start from top

  // Generate grid circles
  const gridCircles = Array.from({ length: levels }, (_, i) => {
    const radius = (maxRadius / levels) * (i + 1);
    return (
      <circle
        key={`grid-${i}`}
        cx={centerX}
        cy={centerY}
        r={radius}
        fill="none"
        stroke="hsl(var(--border))"
        strokeWidth="1"
        strokeDasharray="2,2"
      />
    );
  });

  // Generate axis lines
  const axisLines = data.map((_, index) => {
    const angle = startAngle + index * angleStep;
    const x2 = centerX + maxRadius * Math.cos(angle);
    const y2 = centerY + maxRadius * Math.sin(angle);
    return (
      <line
        key={`axis-${index}`}
        x1={centerX}
        y1={centerY}
        x2={x2}
        y2={y2}
        stroke="hsl(var(--border))"
        strokeWidth="1"
      />
    );
  });

  // Generate data polygon
  const points = data.map((point, index) => {
    const angle = startAngle + index * angleStep;
    const normalizedValue = point.value / (point.maxValue || 100);
    const radius = maxRadius * normalizedValue;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);
    return `${x},${y}`;
  }).join(" ");

  // Generate labels with abbreviated text to prevent cutoff
  const labels = data.map((point, index) => {
    const angle = startAngle + index * angleStep;
    const labelRadius = maxRadius + 25;
    const x = centerX + labelRadius * Math.cos(angle);
    const y = centerY + labelRadius * Math.sin(angle);
    
    // Abbreviate long labels
    const displayLabel = point.category;
    
    return (
      <text
        key={`label-${index}`}
        x={x}
        y={y}
        textAnchor="middle"
        dominantBaseline="middle"
        className="fill-muted-foreground text-[9px] uppercase tracking-wider"
      >
        {displayLabel}
      </text>
    );
  });

  return (
    <div className={cn(
      "relative border border-border bg-card/50 backdrop-blur-sm p-4",
      className
    )}>
      {/* Corner decorations */}
      <span className="absolute -top-px -left-px text-primary text-xs">┌</span>
      <span className="absolute -top-px -right-px text-primary text-xs">┐</span>
      <span className="absolute -bottom-px -left-px text-primary text-xs">└</span>
      <span className="absolute -bottom-px -right-px text-primary text-xs">┘</span>
      
      <div className="flex items-center gap-2 mb-4 pb-2 border-b border-border">
        <span className="text-primary">■</span>
        <span className="text-xs uppercase tracking-widest text-muted-foreground">
          Skill Breakdown
        </span>
      </div>
      
      <div className="flex justify-center">
        <svg width={sizeX} height={sizeY} viewBox={`0 0 ${sizeX} ${sizeY}`}>
          {gridCircles}
          {axisLines}
          <polygon
            points={points}
            fill="hsl(var(--primary) / 0.2)"
            stroke="hsl(var(--primary))"
            strokeWidth="2"
          />
          {labels}
          {/* Data points */}
          {data.map((point, index) => {
            const angle = startAngle + index * angleStep;
            const normalizedValue = point.value / (point.maxValue || 100);
            const radius = maxRadius * normalizedValue;
            const x = centerX + radius * Math.cos(angle);
            const y = centerY + radius * Math.sin(angle);
            return (
              <circle
                key={`point-${index}`}
                cx={x}
                cy={y}
                r="4"
                fill="hsl(var(--primary))"
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
};
