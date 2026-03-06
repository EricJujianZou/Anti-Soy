import { useState, useCallback } from "react";
import { uploadBatch } from "@/services/batchApi";
import { useToast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";
import type { PriorityKey } from "@/services/api";

export const useBatchUpload = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();

  const addFiles = useCallback((newFiles: File[]) => {
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

    setFiles((prev) => {
      const combined = [...prev, ...validFiles];
      if (combined.length > 10) {
        toast({
          title: "Maximum 10 resumes allowed",
          description: "Only the first 10 files will be kept",
          variant: "destructive",
        });
        return combined.slice(0, 10);
      }
      return combined;
    });
  }, [toast]);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = async (priorities: PriorityKey[], useGenericQuestions?: boolean) => {
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      const { batch_id } = await uploadBatch(files, priorities, useGenericQuestions);
      localStorage.setItem("antisoy_batch_id", batch_id);
      localStorage.setItem(`antisoy_batch_${batch_id}_priorities`, JSON.stringify(priorities));
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
    addFiles,
    removeFile,
    handleUpload,
    isUploading,
  };
};
