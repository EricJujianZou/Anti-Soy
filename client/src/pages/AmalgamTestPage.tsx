import { useState, useCallback, useRef } from "react";
import { Header } from "@/components/Header";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/utils/utils";
import { Upload, FileText, Loader2, Download, CheckCircle2, AlertCircle } from "lucide-react";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");

type Status = "idle" | "uploading" | "success" | "error";

const AmalgamTestPage = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");
  const [resumeCount, setResumeCount] = useState<number | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const setSelectedFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setStatus("error");
      setMessage("Only PDF files are supported.");
      return;
    }
    setFile(f);
    setStatus("idle");
    setMessage("");
    setDownloadUrl(null);
    setResumeCount(null);
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
    const f = e.dataTransfer.files[0];
    if (f) setSelectedFile(f);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setSelectedFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;

    setStatus("uploading");
    setMessage("Uploading and parsing — this may take a minute...");
    setDownloadUrl(null);
    setResumeCount(null);

    const formData = new FormData();
    formData.append("pdf", file, file.name);

    try {
      const resp = await fetch(`${API_BASE_URL}/amalgam/test`, {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(body.detail || resp.statusText);
      }

      const count = Number(resp.headers.get("X-Resume-Count") ?? 0);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);

      setResumeCount(count);
      setDownloadUrl(url);
      setStatus("success");
      console.log(`X-Resume-Count: ${resp.headers.get("X-Resume-Count")}`)
      setMessage(`Extracted ${count} resume${count !== 1 ? "s" : ""} successfully.`);
    } catch (err: unknown) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "An unknown error occurred.");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="container mx-auto px-4 py-12 max-w-2xl">
        <div className="text-center mb-8">
          <p className="text-xs text-muted-foreground uppercase tracking-widest mb-2 font-mono">
            internal tool
          </p>
          <h1 className="text-3xl font-bold text-foreground mb-2 uppercase tracking-widest">
            Amalgam PDF Parser
          </h1>
          <p className="text-muted-foreground text-sm">
            Upload a multi-resume PDF to test extraction. Returns individual resume PDFs as a zip.
          </p>
        </div>

        <Card className="border-border bg-card/50 backdrop-blur-sm relative overflow-hidden">
          <span className="absolute -top-px -left-px text-primary text-sm p-1">┌</span>
          <span className="absolute -top-px -right-px text-primary text-sm p-1">┐</span>
          <span className="absolute -bottom-px -left-px text-primary text-sm p-1">└</span>
          <span className="absolute -bottom-px -right-px text-primary text-sm p-1">┘</span>

          <CardContent className="pt-6 flex flex-col gap-6">
            {/* Drop zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={cn(
                "border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-all duration-300",
                isDragging
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              )}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              <div className="flex flex-col items-center gap-3 text-muted-foreground">
                <Upload className="w-8 h-8 text-primary" />
                <p className="text-sm">
                  {file
                    ? "Click or drop to change file"
                    : "Drop amalgam PDF here or click to browse"}
                </p>
              </div>
            </div>

            {/* Selected file */}
            {file && (
              <div className="flex items-center gap-3 bg-muted/40 rounded-lg px-4 py-3 text-sm">
                <FileText className="w-4 h-4 text-primary shrink-0" />
                <span className="text-foreground truncate">{file.name}</span>
                <span className="text-muted-foreground ml-auto shrink-0">
                  {(file.size / 1024).toFixed(1)} KB
                </span>
              </div>
            )}

            {/* Upload button */}
            <button
              onClick={handleUpload}
              disabled={!file || status === "uploading"}
              className={cn(
                "w-full py-3 rounded-lg font-medium text-sm uppercase tracking-widest transition-all",
                "bg-primary text-primary-foreground hover:bg-primary/90",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "flex items-center justify-center gap-2"
              )}
            >
              {status === "uploading" ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Parsing...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Upload &amp; Parse
                </>
              )}
            </button>

            {/* Status feedback */}
            {message && (
              <div
                className={cn(
                  "flex items-start gap-3 rounded-lg px-4 py-3 text-sm",
                  status === "success" && "bg-green-500/10 text-green-400",
                  status === "error" && "bg-red-500/10 text-red-400",
                  status === "uploading" && "bg-muted/40 text-muted-foreground"
                )}
              >
                {status === "success" && <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />}
                {status === "error" && <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                {status === "uploading" && <Loader2 className="w-4 h-4 mt-0.5 shrink-0 animate-spin" />}
                <span>{message}</span>
              </div>
            )}

            {/* Download link */}
            {status === "success" && downloadUrl && (
              <a
                href={downloadUrl}
                download="extracted_resumes.zip"
                className={cn(
                  "flex items-center justify-center gap-2 w-full py-3 rounded-lg text-sm font-medium uppercase tracking-widest",
                  "border border-primary text-primary hover:bg-primary/10 transition-colors"
                )}
              >
                <Download className="w-4 h-4" />
                Download {resumeCount} Resume{resumeCount !== 1 ? "s" : ""} (ZIP)
              </a>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default AmalgamTestPage;
