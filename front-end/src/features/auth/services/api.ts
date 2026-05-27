import { type ApiErrorPayload } from "@/features/auth/types";

export function getApiBaseUrl() {
  return (process.env.API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export async function parseApiError(response: Response) {
  try {
    const body = (await response.json()) as ApiErrorPayload;

    if (typeof body.detail === "string") {
      return body.detail;
    }

    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return body.detail
        .map((error) => error.msg)
        .filter(Boolean)
        .join(" ");
    }
  } catch {
    // Fall back to a status-based message below.
  }

  return response.statusText || "The request could not be completed.";
}
