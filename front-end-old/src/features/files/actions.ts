"use server";

import { cookies } from "next/headers";
import { getApiBaseUrl } from "@/features/auth/services/api";
import { ACCESS_TOKEN_COOKIE } from "@/features/auth/services/cookies";

export async function getPresignedUploadUrl(filename: string, contentType: string) {
  const cookieStore = await cookies();
  const token = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;

  if (!token) {
    throw new Error("Unauthorized: No access token found.");
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1/file/presigned-url`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify({
      filename,
      operation: "upload",
      content_type: contentType,
      expires_in: 3600,
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to get presigned URL: ${errorText || response.statusText}`);
  }

  return (await response.json()) as { url: string; key: string };
}
