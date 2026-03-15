import { useState, useCallback, useRef } from "react";
import { Header } from "@/components/Header";
import { useBatchUpload } from "@/hooks/useBatchUpload";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/utils";
import { X, Upload, FileText, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { DEFAULT_SCORING_CONFIG, type ScoringConfig } from "@/services/api";

// ─── Tech stack options ───────────────────────────────────────────────────────

const LANGUAGE_OPTIONS = [
  "React", "Angular", "Vue", "Svelte", "Python", "Go", "Rust", "Java", "C#",
  "TypeScript", "JavaScript", "Node.js", "Django", "Flask", "FastAPI", "Spring",
  ".NET", "Next.js", "Express", "Ruby on Rails", "Swift", "Kotlin",
];

const TOOL_OPTIONS = [
  "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD",
  "PostgreSQL", "MongoDB", "Redis", "GraphQL", "REST API",
  "Microsoft 365/Dynamics", "Elasticsearch", "RabbitMQ", "Kafka",
];

const MAX_TECH_SELECTIONS = 5;

// ─── Slider row ───────────────────────────────────────────────────────────────

interface SliderRowProps {
  label: string;
  description: string;
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}

const SliderRow = ({ label, description, value, onChange, disabled }: SliderRowProps) => (
  <div className="space-y-2">
    <div className="flex justify-between items-center">
      <div>
        <span className="text-sm font-medium text-foreground">{label}</span>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <span className="text-sm font-mono text-primary tabular-nums w-8 text-right">{value.toFixed(1)}</span>
    </div>
    <div className="flex items-center gap-3">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider w-12 text-right">Lenient</span>
      <Slider
        min={0}
        max={1}
        step={0.1}
        value={[value]}
        onValueChange={([v]) => onChange(v)}
        disabled={disabled}
        className="flex-1"
      />
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider w-8">Strict</span>
    </div>
  </div>
);

// ─── Tech multiselect ─────────────────────────────────────────────────────────

interface TechMultiselectProps {
  label: string;
  options: string[];
  selected: string[];
  onChange: (vals: string[]) => void;
  disabled?: boolean;
}

const TechMultiselect = ({ label, options, selected, onChange, disabled }: TechMultiselectProps) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const atMax = selected.length >= MAX_TECH_SELECTIONS;

  const toggle = (option: string) => {
    if (selected.includes(option)) {
      onChange(selected.filter((s) => s !== option));
    } else if (!atMax) {
      onChange([...selected, option]);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className="text-xs text-muted-foreground">{selected.length}/{MAX_TECH_SELECTIONS}</span>
      </div>

      {/* Selected pills */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((s) => (
            <Badge
              key={s}
              variant="outline"
              className="border-primary/40 text-primary text-xs cursor-pointer hover:bg-destructive/10 hover:text-destructive hover:border-destructive/40 transition-colors"
              onClick={() => !disabled && toggle(s)}
            >
              {s} <X className="w-2.5 h-2.5 ml-1" />
            </Badge>
          ))}
        </div>
      )}

      {/* Dropdown trigger */}
      <div className="relative" ref={ref}>
        <button
          type="button"
          disabled={disabled}
          onClick={() => setOpen((o) => !o)}
          className={cn(
            "w-full flex items-center justify-between px-3 py-2 text-sm border border-border rounded bg-card/50",
            "hover:border-primary/50 transition-colors",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            open && "border-primary/70"
          )}
        >
          <span className="text-muted-foreground">
            {atMax ? "Maximum 5 selections" : "Select..."}
          </span>
          {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
        </button>

        {open && (
          <div className="absolute z-50 w-full mt-1 border border-border rounded bg-card shadow-lg max-h-48 overflow-y-auto custom-scrollbar">
            {options.map((opt) => {
              const isSelected = selected.includes(opt);
              const isDisabled = !isSelected && atMax;
              return (
                <button
                  key={opt}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => toggle(opt)}
                  className={cn(
                    "w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors",
                    isSelected ? "bg-primary/10 text-primary" : "hover:bg-muted/50 text-foreground",
                    isDisabled && "opacity-40 cursor-not-allowed"
                  )}
                  title={isDisabled ? "Maximum 5 selections" : undefined}
                >
                  <span className={cn(
                    "w-3.5 h-3.5 rounded-sm border flex-shrink-0 flex items-center justify-center text-[10px]",
                    isSelected ? "bg-primary border-primary text-primary-foreground" : "border-muted-foreground/40"
                  )}>
                    {isSelected && "✓"}
                  </span>
                  {opt}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────

const UploadPage = () => {
  const { files, addFiles, removeFile, handleUpload, isUploading } = useBatchUpload();
  const [isDragging, setIsDragging] = useState(false);
  const [useGenericQuestions, setUseGenericQuestions] = useState(false);
  const [scoringConfig, setScoringConfig] = useState<ScoringConfig>(DEFAULT_SCORING_CONFIG);

  const updateWeight = (key: keyof ScoringConfig["weights"], value: number) => {
    setScoringConfig((prev) => ({
      ...prev,
      weights: { ...prev.weights, [key]: value },
    }));
  };

  const setRequiredLanguages = (langs: string[]) => {
    setScoringConfig((prev) => ({
      ...prev,
      required_tech: { ...prev.required_tech, languages: langs },
    }));
  };

  const setRequiredTools = (tools: string[]) => {
    setScoringConfig((prev) => ({
      ...prev,
      required_tech: { ...prev.required_tech, tools },
    }));
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  }, [addFiles]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(Array.from(e.target.files));
  }, [addFiles]);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container mx-auto px-4 py-12 max-w-3xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2 uppercase tracking-widest">
            Upload Candidate Resumes
          </h1>
          <p className="text-muted-foreground">
            Upload up to 10 resumes to analyze candidates in batch
          </p>
        </div>

        <Card className="border-border bg-card/50 backdrop-blur-sm relative overflow-hidden">
          <span className="absolute -top-px -left-px text-primary text-sm p-1">┌</span>
          <span className="absolute -top-px -right-px text-primary text-sm p-1">┐</span>
          <span className="absolute -bottom-px -left-px text-primary text-sm p-1">└</span>
          <span className="absolute -bottom-px -right-px text-primary text-sm p-1">┘</span>

          <CardContent className="pt-6 space-y-8">
            {/* ── Drop zone ── */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={cn(
                "border-2 border-dashed rounded-lg p-12 text-center transition-all duration-300",
                isDragging ? "border-primary bg-primary/5 glow-amber" : "border-border hover:border-primary/50",
                files.length >= 10 && "opacity-50 cursor-not-allowed"
              )}
            >
              <input
                type="file"
                multiple
                accept=".pdf,.docx"
                onChange={handleFileChange}
                disabled={files.length >= 10 || isUploading}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className={cn(
                  "flex flex-col items-center cursor-pointer",
                  files.length >= 10 && "cursor-not-allowed"
                )}
              >
                <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4 text-primary">
                  <Upload className="w-8 h-8" />
                </div>
                <p className="text-lg font-medium mb-1">
                  {isDragging ? "Drop files here" : "Click to browse or drag and drop"}
                </p>
                <p className="text-sm text-muted-foreground">Supported formats: .pdf, .docx</p>
              </label>
            </div>

            {/* ── Scoring Weights ── */}
            <div className="p-4 border border-border/50 rounded-lg bg-muted/5 space-y-5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-widest text-primary">
                  Scoring Weights
                </span>
                <div className="flex-1 border-t border-border/30" />
              </div>

              <SliderRow
                label="AI Detection"
                description="How harshly to penalize AI-generated code"
                value={scoringConfig.weights.ai_detection}
                onChange={(v) => updateWeight("ai_detection", v)}
                disabled={isUploading}
              />
              <SliderRow
                label="Security"
                description="How harshly to penalize security issues"
                value={scoringConfig.weights.security}
                onChange={(v) => updateWeight("security", v)}
                disabled={isUploading}
              />
              <SliderRow
                label="Code Quality"
                description="How harshly to penalize poor code quality"
                value={scoringConfig.weights.code_quality}
                onChange={(v) => updateWeight("code_quality", v)}
                disabled={isUploading}
              />
              <SliderRow
                label="Originality"
                description="How harshly to penalize unoriginal projects"
                value={scoringConfig.weights.originality}
                onChange={(v) => updateWeight("originality", v)}
                disabled={isUploading}
              />

              <div className="pt-2 border-t border-border/30">
                <label className="flex items-center gap-2 cursor-pointer select-none group w-fit">
                  <Checkbox
                    checked={scoringConfig.shipped_to_prod_bonus}
                    onCheckedChange={(checked) =>
                      setScoringConfig((prev) => ({ ...prev, shipped_to_prod_bonus: checked === true }))
                    }
                    disabled={isUploading}
                    className="border-primary/60 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                  />
                  <div>
                    <span className="text-sm font-medium text-foreground group-hover:text-foreground transition-colors">
                      Shipped to Prod bonus
                    </span>
                    <p className="text-xs text-muted-foreground">Reward candidates who have shipped projects to production</p>
                  </div>
                </label>
              </div>
            </div>

            {/* ── Required Tech Stack ── */}
            <div className="p-4 border border-border/50 rounded-lg bg-muted/5 space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-widest text-primary">
                  Required Tech Stack
                </span>
                <div className="flex-1 border-t border-border/30" />
              </div>
              <p className="text-xs text-muted-foreground -mt-2">
                Candidates with hand-coded projects using these technologies score higher. Leave empty to skip.
              </p>

              <TechMultiselect
                label="Required Languages / Frameworks"
                options={LANGUAGE_OPTIONS}
                selected={scoringConfig.required_tech.languages}
                onChange={setRequiredLanguages}
                disabled={isUploading}
              />
              <TechMultiselect
                label="Required Tools / Infrastructure"
                options={TOOL_OPTIONS}
                selected={scoringConfig.required_tech.tools}
                onChange={setRequiredTools}
                disabled={isUploading}
              />
            </div>

            {/* ── Generic questions toggle ── */}
            <div className="pt-2 border-t border-border/30">
              <label className="flex items-center gap-2 cursor-pointer select-none group w-fit mx-auto">
                <Checkbox
                  checked={useGenericQuestions}
                  onCheckedChange={(checked) => setUseGenericQuestions(checked === true)}
                  disabled={isUploading}
                  className="border-primary/60 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                />
                <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                  Use same interview questions for all candidates
                </span>
              </label>
            </div>

            {/* ── File list ── */}
            <div>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-bold uppercase tracking-widest text-primary">Selected Files</h3>
                <span className={cn(
                  "text-xs font-mono",
                  files.length >= 10 ? "text-destructive" : "text-muted-foreground"
                )}>
                  {files.length} / 10 resumes selected
                </span>
              </div>

              {files.length === 0 ? (
                <div className="text-center py-8 border border-border/50 rounded-lg bg-muted/5">
                  <p className="text-sm text-muted-foreground italic">No files selected</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
                  {files.map((file, index) => (
                    <div
                      key={`${file.name}-${index}`}
                      className="flex items-center justify-between p-3 border border-border rounded bg-card/80 group animate-in fade-in slide-in-from-left-2 duration-300"
                    >
                      <div className="flex items-center gap-3 overflow-hidden">
                        <FileText className="w-4 h-4 text-primary shrink-0" />
                        <div className="flex flex-col min-w-0">
                          <span className="text-sm font-medium truncate">{file.name}</span>
                          <span className="text-xs text-muted-foreground">{formatFileSize(file.size)}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => removeFile(index)}
                        className="p-1 hover:bg-destructive/10 hover:text-destructive rounded transition-colors"
                        title="Remove file"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── Submit ── */}
            <div className="flex justify-center">
              <button
                onClick={() => handleUpload(scoringConfig, useGenericQuestions)}
                disabled={files.length === 0 || isUploading}
                className={cn(
                  "w-full sm:w-2/3 border border-primary bg-primary/10 text-primary py-3 px-8",
                  "uppercase tracking-widest text-sm font-bold",
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

                {isUploading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing...
                  </span>
                ) : (
                  "[ run analysis ]"
                )}
              </button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default UploadPage;
