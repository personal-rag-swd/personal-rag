"use server";

import { revalidatePath } from "next/cache";

import { getApiBaseUrl, parseApiError } from "@/features/auth/services/api";
import { getAccessToken, mapNotebook } from "@/features/notebooks/api";
import {
  notebookSchema,
  type Notebook,
  type NotebookActionState,
  type NotebookApiPayload,
} from "@/features/notebooks/types";

function formDataToObject(formData: FormData) {
  return Object.fromEntries(formData.entries());
}

function parseTags(value: string) {
  const seen = new Set<string>();
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter((tag) => {
      const key = tag.toLowerCase();
      if (!tag || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function getFieldErrors(
  error: { flatten: () => { fieldErrors: Record<string, string[] | undefined> } }
): NotebookActionState["fieldErrors"] {
  const { fieldErrors } = error.flatten();

  return {
    name: fieldErrors.name?.[0],
    description: fieldErrors.description?.[0],
    tags: fieldErrors.tags?.[0],
  };
}

export async function createNotebookAction(
  _prevState: NotebookActionState,
  formData: FormData
): Promise<NotebookActionState> {
  const parsed = notebookSchema.safeParse(formDataToObject(formData));
  const values = {
    name: typeof formData.get("name") === "string" ? String(formData.get("name")) : "",
    description:
      typeof formData.get("description") === "string" ? String(formData.get("description")) : "",
    tags: typeof formData.get("tags") === "string" ? String(formData.get("tags")) : "",
  };

  if (!parsed.success) {
    return {
      values,
      formError: "Invalid format",
      fieldErrors: getFieldErrors(parsed.error),
    };
  }

  const token = await getAccessToken();
  if (!token) {
    return {
      values,
      formError: "You need to sign in before creating a notebook.",
    };
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/notebooks/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: parsed.data.name,
        description: parsed.data.description,
        tags: parseTags(parsed.data.tags),
      }),
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        values,
        formError: await parseApiError(response),
      };
    }

    revalidatePath("/dashboard");
    return {
      notebook: mapNotebook((await response.json()) as NotebookApiPayload),
    };
  } catch {
    return {
      values,
      formError: "Could not reach the API. Check API_BASE_URL and try again.",
    };
  }
}

export async function updateNotebookAction(
  _prevState: NotebookActionState,
  formData: FormData
): Promise<NotebookActionState> {
  const id = typeof formData.get("id") === "string" ? String(formData.get("id")) : "";
  const parsed = notebookSchema.safeParse(formDataToObject(formData));
  const values = {
    name: typeof formData.get("name") === "string" ? String(formData.get("name")) : "",
    description:
      typeof formData.get("description") === "string" ? String(formData.get("description")) : "",
    tags: typeof formData.get("tags") === "string" ? String(formData.get("tags")) : "",
  };

  if (!parsed.success) {
    return {
      values,
      formError: "Invalid format",
      fieldErrors: getFieldErrors(parsed.error),
    };
  }

  const token = await getAccessToken();
  if (!token) {
    return {
      values,
      formError: "You need to sign in before updating a notebook.",
    };
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/notebooks/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: parsed.data.name,
        description: parsed.data.description,
        tags: parseTags(parsed.data.tags),
      }),
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        values,
        formError: await parseApiError(response),
      };
    }

    revalidatePath("/dashboard");
    return {
      notebook: mapNotebook((await response.json()) as NotebookApiPayload),
    };
  } catch {
    return {
      values,
      formError: "Could not reach the API. Check API_BASE_URL and try again.",
    };
  }
}


export async function touchNotebookAction(id: string): Promise<Notebook> {
  const token = await getAccessToken();
  if (!token) {
    throw new Error("Unauthorized");
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1/notebooks/${id}/touch`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return mapNotebook((await response.json()) as NotebookApiPayload);
}

export async function deleteNotebookAction(id: string): Promise<void> {
  const token = await getAccessToken();
  if (!token) {
    throw new Error("Unauthorized");
  }

  const response = await fetch(`${getApiBaseUrl()}/api/v1/notebooks/${id}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  revalidatePath("/dashboard");
}
