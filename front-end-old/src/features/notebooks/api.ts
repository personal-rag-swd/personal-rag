import "server-only";

import { cookies } from "next/headers";

import { getApiBaseUrl, parseApiError } from "@/features/auth/services/api";
import { ACCESS_TOKEN_COOKIE } from "@/features/auth/services/cookies";
import { type Notebook, type NotebookApiPayload } from "@/features/notebooks/types";

export function mapNotebook(payload: NotebookApiPayload): Notebook {
  return {
    id: payload.id,
    name: payload.name,
    description: payload.description,
    documentCount: payload.document_count,
    queryCount: payload.query_count,
    createdAt: payload.created_at,
    lastActiveAt: payload.last_active_at,
    tags: payload.tags,
  };
}

export async function getAccessToken() {
  const cookieStore = await cookies();
  return cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;
}

export async function listNotebooks(): Promise<Notebook[]> {
  const token = await getAccessToken();
  if (!token) return [];

  const response = await fetch(`${getApiBaseUrl()}/api/v1/notebooks/`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  const notebooks = (await response.json()) as NotebookApiPayload[];
  return notebooks.map(mapNotebook);
}
