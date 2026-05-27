"use client";

import * as React from "react";
import { toast } from "sonner";
import { 
  UploadCloudIcon, 
  FileIcon, 
  CircleCheckIcon, 
  AlertCircleIcon, 
  Loader2Icon,
  PlusIcon
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { getPresignedUploadUrl } from "@/features/files/actions";

// Max file size: 10MB
const MAX_FILE_SIZE = 10 * 1024 * 1024; 

type UploadStatus = "idle" | "selected" | "uploading" | "success" | "error";

export function UploadFileDialog() {
  const [open, setOpen] = React.useState(false);
  const [file, setFile] = React.useState<File | null>(null);
  const [status, setStatus] = React.useState<UploadStatus>("idle");
  const [progress, setProgress] = React.useState(0);
  const [errorMessage, setErrorMessage] = React.useState("");
  const [isDragOver, setIsDragOver] = React.useState(false);
  
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const xhrRef = React.useRef<XMLHttpRequest | null>(null);

  const resetState = () => {
    setFile(null);
    setStatus("idle");
    setProgress(0);
    setErrorMessage("");
    setIsDragOver(false);
    if (xhrRef.current) {
      xhrRef.current.abort();
      xhrRef.current = null;
    }
  };

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen);
    if (!isOpen) {
      resetState();
    }
  };

  const validateFile = (selectedFile: File): boolean => {
    if (selectedFile.size > MAX_FILE_SIZE) {
      toast.error("File is too large", {
        description: "Maximum file size allowed is 10MB.",
      });
      return false;
    }
    return true;
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      if (validateFile(selectedFile)) {
        setFile(selectedFile);
        setStatus("selected");
      }
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const onDragLeave = () => {
    setIsDragOver(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      if (validateFile(droppedFile)) {
        setFile(droppedFile);
        setStatus("selected");
      }
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = async () => {
    if (!file) return;

    setStatus("uploading");
    setProgress(0);

    try {
      // 1. Get S3 presigned URL
      const { url } = await getPresignedUploadUrl(file.name, file.type);

      // 2. Upload file directly to S3 via XMLHTTPRequest for progress monitoring
      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      xhr.open("PUT", url, true);
      xhr.setRequestHeader("Content-Type", file.type);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          setProgress(percentComplete);
        }
      };

      xhr.onload = () => {
        if (xhr.status === 200) {
          setStatus("success");
          toast.success("Upload complete!", {
            description: `Successfully uploaded ${file.name}`,
          });
        } else {
          setStatus("error");
          setErrorMessage(`Storage upload failed: HTTP ${xhr.status} ${xhr.statusText}`);
          toast.error("Upload failed", {
            description: `Server returned status ${xhr.status}`,
          });
        }
      };

      xhr.onerror = () => {
        setStatus("error");
        setErrorMessage("A network error occurred during file upload.");
        toast.error("Network error", {
          description: "Could not reach storage provider. Check your internet connection.",
        });
      };

      xhr.send(file);

    } catch (error) {
      const err = error as Error;
      setStatus("error");
      setErrorMessage(err.message || "Failed to initiate upload.");
      toast.error("Upload initiation failed", {
        description: err.message || "An unexpected error occurred.",
      });
    }
  };

  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={
        <Button variant="outline" size="sm" className="bg-primary/5 hover:bg-primary/10 border-primary/20 hover:border-primary/40 text-primary transition-all">
          <PlusIcon />
          <span>Upload File</span>
        </Button>
      } />
      <DialogContent className="sm:max-w-md select-none">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">Upload Document</DialogTitle>
          <DialogDescription className="text-muted-foreground mt-1">
            Securely upload files to S3 using single-use presigned URLs.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {status === "idle" && (
            <div
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={triggerFileSelect}
              className={`group border-2 border-dashed rounded-2xl flex flex-col items-center justify-center p-10 cursor-pointer gap-3 transition-all duration-300 ${
                isDragOver
                  ? "border-primary bg-primary/5 scale-[0.98] ring-4 ring-primary/10"
                  : "border-muted-foreground/30 hover:border-primary/50 bg-muted/10 hover:bg-muted/20"
              }`}
            >
              <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="size-12 rounded-full bg-primary/10 flex items-center justify-center text-primary group-hover:scale-110 transition-transform duration-300">
                <UploadCloudIcon className="size-6" />
              </div>
              <div className="text-center">
                <p className="font-medium text-sm text-foreground">
                  Drag & drop your file here
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  or click to select from your computer
                </p>
              </div>
              <p className="text-[10px] text-muted-foreground/80 mt-2">
                Supported formats: PDF, TXT, DOCX, etc. (Max 10MB)
              </p>
            </div>
          )}

          {status === "selected" && file && (
            <div className="border border-border bg-muted/10 rounded-2xl p-6 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
                  <FileIcon className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm text-foreground truncate" title={file.name}>
                    {file.name}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {formatBytes(file.size)}
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-end gap-2 mt-2">
                <Button variant="ghost" size="sm" onClick={resetState}>
                  Cancel
                </Button>
                <Button size="sm" onClick={handleUpload}>
                  Upload File
                </Button>
              </div>
            </div>
          )}

          {status === "uploading" && file && (
            <div className="border border-border bg-muted/10 rounded-2xl p-6 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <Loader2Icon className="size-5 text-primary animate-spin shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm text-foreground truncate">
                    Uploading {file.name}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Please keep this window open
                  </p>
                </div>
                <span className="text-sm font-semibold text-primary">{progress}%</span>
              </div>
              <div className="w-full bg-muted/60 h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-primary h-full rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex justify-end mt-2">
                <Button variant="ghost" size="sm" className="text-destructive hover:bg-destructive/10" onClick={resetState}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {status === "success" && (
            <div className="border border-green-500/20 bg-green-500/5 dark:bg-green-500/10 rounded-2xl p-8 flex flex-col items-center text-center gap-4 animate-in fade-in-50 duration-300">
              <div className="size-12 rounded-full bg-green-500/10 text-green-500 flex items-center justify-center animate-bounce">
                <CircleCheckIcon className="size-6" />
              </div>
              <div>
                <p className="font-semibold text-lg text-foreground">Upload Success</p>
              </div>
              <div className="flex justify-center w-full mt-2">
                <DialogClose render={<Button size="sm" />}>
                  Close
                </DialogClose>
              </div>
            </div>
          )}

          {status === "error" && (
            <div className="border border-destructive/20 bg-destructive/5 dark:bg-destructive/10 rounded-2xl p-6 flex flex-col items-center text-center gap-4 animate-in fade-in-50 duration-300">
              <div className="size-12 rounded-full bg-destructive/10 text-destructive flex items-center justify-center">
                <AlertCircleIcon className="size-6" />
              </div>
              <div>
                <p className="font-semibold text-base text-foreground">Upload Failed</p>
                <p className="text-xs text-destructive/80 mt-1 max-w-xs break-words">
                  {errorMessage || "An unexpected error occurred."}
                </p>
              </div>
              <div className="flex justify-end gap-2 w-full mt-2">
                <Button variant="ghost" size="sm" onClick={resetState}>
                  Cancel
                </Button>
                <Button size="sm" variant="destructive" onClick={handleUpload}>
                  Try Again
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
