import { useState, useCallback } from "react";
import { uploadBatch } from "@/services/batchApi";
import { useToast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";
import type { ScoringConfig } from "@/services/api";

export type UploadMode = "individual" | "merged";

export const useBatchUpload = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploadMode, setUploadMode] = useState<UploadMode>("individual");
  const [isUploading, setIsUploading] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();

  const addFiles = useCallback((newFiles: File[]) => {
    setFiles((prev) => {
      if (uploadMode === "merged") {
        // Merged mode: exactly 1 PDF
        const pdfFile = newFiles.find(
          (f) => f.type === "application/pdf" || f.name.endsWith(".pdf"),
        );
        if (!pdfFile) {
          toast({
            title: "Invalid file type",
            description: "Merged mode only accepts PDF files",
            variant: "destructive",
          });
          return prev;
        }
        return [pdfFile]; // replace any existing file
      }

      // Individual mode: up to 100, .pdf or .docx
      const validFiles = newFiles.filter((file) => {
        const isValidType =
          file.type === "application/pdf" ||
          file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
          file.name.endsWith(".pdf") ||
          file.name.endsWith(".docx");

        if (!isValidType) {
          toast({
            title: "Invalid file type",
            description: `${file.name} is not a .pdf or .docx file`,
            variant: "destructive",
          });
        }
        return isValidType;
      });

      const combined = [...prev, ...validFiles];
      if (combined.length > 100) {
        toast({
          title: "Maximum 100 resumes allowed",
          description: "Only the first 100 files will be kept",
          variant: "destructive",
        });
        return combined.slice(0, 100);
      }
      return combined;
    });
  }, [toast, uploadMode]);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const changeUploadMode = useCallback((mode: UploadMode) => {
    setUploadMode(mode);
    setFiles([]); // clear files when switching modes
  }, []);

  const handleUpload = async (scoringConfig: ScoringConfig, useGenericQuestions?: boolean) => {
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      const { batch_id } = await uploadBatch(files, scoringConfig, useGenericQuestions, uploadMode);
      localStorage.setItem("antisoy_batch_id", batch_id);
      localStorage.setItem(`antisoy_batch_${batch_id}_scoring_config`, JSON.stringify(scoringConfig));
      navigate(`/dashboard/${batch_id}`, { replace: true });
    } catch (error) {
      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : "Please try again.",
        variant: "destructive",
      });
      setIsUploading(false);
    }
  };

  return {
    files,
    uploadMode,
    changeUploadMode,
    addFiles,
    removeFile,
    handleUpload,
    isUploading,
  };
};
