import { apiFetch } from "@/lib/api-client";

interface PresignedUploadUrl {
  url: string;
  key: string;
}

export async function getPresignedUploadUrl(
  filename: string,
  contentType: string,
  notebookId?: string
): Promise<PresignedUploadUrl> {
  return apiFetch<PresignedUploadUrl>("/api/v1/file/presigned-url", {
    method: "POST",
    data: {
      filename,
      operation: "upload",
      content_type: contentType,
      notebook_id: notebookId,
      expires_in: 3600,
    },
  });
}

export async function reportUploadFailed(
  key: string,
  notebookId?: string,
  errorMessage?: string
): Promise<{ status: string; updated: boolean }> {
  return apiFetch<{ status: string; updated: boolean }>("/api/v1/file/upload-failed", {
    method: "POST",
    data: {
      key,
      notebook_id: notebookId,
      error_message: errorMessage,
    },
  });
}
