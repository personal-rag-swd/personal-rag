import { apiFetch } from "@/lib/api-client";

interface PresignedUploadUrl {
  url: string;
  key: string;
}

export async function getPresignedUploadUrl(
  filename: string,
  contentType: string
): Promise<PresignedUploadUrl> {
  return apiFetch<PresignedUploadUrl>("/api/v1/file/presigned-url", {
    method: "POST",
    data: {
      filename,
      operation: "upload",
      content_type: contentType,
      expires_in: 3600,
    },
  });
}
