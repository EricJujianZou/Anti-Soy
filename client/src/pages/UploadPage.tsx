import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Header } from "@/components/Header";
import { useBatchUpload } from "@/hooks/useBatchUpload";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/utils/utils";
import { X, Upload, FileText, Loader2 } from "lucide-react";
import { PRIORITY_OPTIONS, type PriorityKey } from "@/services/api";

const UploadPage = () => {
  const { files, addFiles, removeFile, handleUpload, isUploading } = useBatchUpload();
  const [isDragging, setIsDragging] = useState(false);
  const [searchParams] = useSearchParams();
  const [priorities, setPriorities] = useState<Set<PriorityKey>>(
    new Set(PRIORITY_OPTIONS.map((o) => o.key))
  );

  useEffect(() => {
    const prioritiesParam = searchParams.get("priorities");
    if (prioritiesParam) {
      const keys = prioritiesParam.split(",").filter((k): k is PriorityKey => 
        PRIORITY_OPTIONS.some(opt => opt.key === k)
      );
      if (keys.length > 0) {
        setPriorities(new Set(keys));
      }
    }
  }, [searchParams]);

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
    const droppedFiles = Array.from(e.dataTransfer.files);
    addFiles(droppedFiles);
  }, [addFiles]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
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
          {/* Corner decorations */}
          <span className="absolute -top-px -left-px text-primary text-sm p-1">┌</span>
          <span className="absolute -top-px -right-px text-primary text-sm p-1">┐</span>
          <span className="absolute -bottom-px -left-px text-primary text-sm p-1">└</span>
          <span className="absolute -bottom-px -right-px text-primary text-sm p-1">┘</span>

          <CardContent className="pt-6">
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
                <p className="text-sm text-muted-foreground">
                  Supported formats: .pdf, .docx
                </p>
              </label>
            </div>

            {/* Evaluation Priorities */}
            <div className="mt-8 p-4 border border-border/50 rounded-lg bg-muted/5">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs font-bold uppercase tracking-widest text-primary">
                  Analysis Priorities
                </span>
                <div className="flex-1 border-t border-border/30" />
              </div>
              <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3">
                {PRIORITY_OPTIONS.map((opt) => (
                  <label
                    key={opt.key}
                    className="flex items-center gap-2 cursor-pointer select-none group"
                  >
                    <Checkbox
                      checked={priorities.has(opt.key)}
                      onCheckedChange={() => togglePriority(opt.key)}
                      disabled={isUploading}
                      className="border-primary/60 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                    />
                    <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                      {opt.label}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-8">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-bold uppercase tracking-widest text-primary">
                  Selected Files
                </h3>
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

            <div className="mt-8 flex justify-center">
              <button
                onClick={() => handleUpload(Array.from(priorities))}
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
