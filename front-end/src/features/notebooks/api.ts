import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import type { ThreadMessage } from "@assistant-ui/core"
import { apiFetch } from "@/lib/api-client"
import {
  type Notebook,
  type NotebookApiPayload,
  type NotebookPopulateApiPayload,
  type NotebookDocument,
  type NotebookDocumentApiPayload,
  type NotebookReport,
  type NotebookReportApiPayload,
  type ReportType,
} from "./types"

function mapNotebookReport(payload: NotebookReportApiPayload): NotebookReport {
  return {
    id: payload.id,
    notebookId: payload.notebook_id,
    reportType: payload.report_type,
    content: payload.content,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  }
}

export function mapNotebook(payload: NotebookApiPayload): Notebook {
  return {
    id: payload.id,
    name: payload.name,
    description: payload.description,
    createdAt: payload.created_at,
    lastActiveAt: payload.last_active_at,
    tags: payload.tags,
  }
}

export async function populateNotebook(
  notebookId: string
): Promise<{ documentCount: number; queryCount: number }> {
  const data = await apiFetch<NotebookPopulateApiPayload>(
    `/api/v1/notebooks/${notebookId}/populate`
  )
  return {
    documentCount: data.document_count,
    queryCount: data.query_count,
  }
}

function mapNotebookDocument(
  payload: NotebookDocumentApiPayload
): NotebookDocument {
  return {
    id: payload.id,
    notebookId: payload.notebook_id,
    filename: payload.filename,
    contentType: payload.content_type,
    size: payload.size,
    status: payload.status,
    errorMessage: payload.error_message,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  }
}

export function useNotebooksQuery() {
  return useQuery<Notebook[]>({
    queryKey: ["notebooks"],
    queryFn: async () => {
      const data = await apiFetch<NotebookApiPayload[]>("/api/v1/notebooks/")
      return data.map(mapNotebook)
    },
  })
}

export function useCreateNotebookMutation() {
  const queryClient = useQueryClient()
  return useMutation<
    Notebook,
    Error,
    { name: string; description: string; tags: string[] }
  >({
    mutationFn: async (variables: {
      name: string
      description: string
      tags: string[]
    }) => {
      const data = await apiFetch<NotebookApiPayload>("/api/v1/notebooks/", {
        method: "POST",
        data: variables,
      })
      return mapNotebook(data)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] })
    },
  })
}

export function useUpdateNotebookMutation() {
  const queryClient = useQueryClient()
  return useMutation<
    Notebook,
    Error,
    { id: string; name: string; description: string; tags: string[] }
  >({
    mutationFn: async ({
      id,
      ...variables
    }: {
      id: string
      name: string
      description: string
      tags: string[]
    }) => {
      const data = await apiFetch<NotebookApiPayload>(
        `/api/v1/notebooks/${id}`,
        {
          method: "PATCH",
          data: variables,
        }
      )
      return mapNotebook(data)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] })
    },
  })
}

export function useDeleteNotebookMutation() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (id: string) => {
      await apiFetch(`/api/v1/notebooks/${id}`, {
        method: "DELETE",
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] })
    },
  })
}

export function useNotebookQuery(id: string | undefined) {
  return useQuery<Notebook>({
    queryKey: ["notebooks", id],
    queryFn: async () => {
      const data = await apiFetch<NotebookApiPayload>(`/api/v1/notebooks/${id}`)
      return mapNotebook(data)
    },
    enabled: Boolean(id),
  })
}

const ACTIVE_DOCUMENT_STATUSES = new Set(["pending", "uploaded", "processing"])

export function useNotebookDocumentsQuery(notebookId: string | undefined) {
  return useQuery<NotebookDocument[]>({
    queryKey: ["notebooks", notebookId, "documents"],
    queryFn: async () => {
      const data = await apiFetch<NotebookDocumentApiPayload[]>(
        `/api/v1/notebooks/${notebookId}/documents`
      )
      return data.map(mapNotebookDocument)
    },
    enabled: Boolean(notebookId),
    // Poll quickly while documents are still being ingested so the lifecycle
    // progress stays live, then back off once everything settles.
    refetchInterval: (query) => {
      const docs = query.state.data
      const hasActive = docs?.some((doc) =>
        ACTIVE_DOCUMENT_STATUSES.has(doc.status)
      )
      return hasActive ? 2000 : 8000
    },
  })
}

export function useDeleteNotebookDocumentMutation() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { notebookId: string; documentId: string }>({
    mutationFn: async ({ notebookId, documentId }) => {
      await apiFetch(
        `/api/v1/notebooks/${notebookId}/documents/${documentId}`,
        {
          method: "DELETE",
        }
      )
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["notebooks", variables.notebookId, "documents"],
      })
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] })
    },
  })
}

export function useTouchNotebookMutation() {
  const queryClient = useQueryClient()
  return useMutation<Notebook, Error, string>({
    mutationFn: async (id: string) => {
      const data = await apiFetch<NotebookApiPayload>(
        `/api/v1/notebooks/${id}/touch`,
        {
          method: "POST",
        }
      )
      return mapNotebook(data)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] })
    },
  })
}

type NotebookChatHistoryMessage = {
  role: "user" | "assistant"
  parts: { type: "text" | "reasoning"; content: string }[]
  sources?: {
    filename: string
    document_id: string
    chunk_index: number
    content: string
  }[]
  references?: {
    ref_id: string
    citation_number: number
    filename: string
    document_id: string
    chunk_index: number
    content: string
  }[]
}

export function useNotebookReportsQuery(notebookId: string | undefined) {
  return useQuery<NotebookReport[]>({
    queryKey: ["notebooks", notebookId, "reports"],
    queryFn: async () => {
      const data = await apiFetch<NotebookReportApiPayload[]>(
        `/api/v1/notebooks/${notebookId}/reports`
      )
      return data.map(mapNotebookReport)
    },
    enabled: Boolean(notebookId),
  })
}

export function useGenerateNotebookReportMutation(notebookId: string) {
  const queryClient = useQueryClient()
  return useMutation<
    NotebookReport,
    Error,
    { reportType: ReportType; additionalInstructions?: string }
  >({
    mutationFn: async ({ reportType, additionalInstructions }) => {
      const data = await apiFetch<NotebookReportApiPayload>(
        `/api/v1/notebooks/${notebookId}/reports`,
        {
          method: "POST",
          data: {
            report_type: reportType,
            additional_instructions: additionalInstructions,
          },
        }
      )
      return mapNotebookReport(data)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["notebooks", notebookId, "reports"],
      })
    },
  })
}

export async function fetchNotebookChatHistory(
  notebookId: string
): Promise<ThreadMessage[]> {
  const data = await apiFetch<NotebookChatHistoryMessage[]>(
    `/api/v1/notebooks/${notebookId}/chat/history?include_reasoning=true`
  )
  const now = Date.now()

  return data.map((message, index): ThreadMessage => {
    const base = {
      id: `${notebookId}-${index}`,
      createdAt: new Date(now + index),
      metadata: { custom: {} },
    }

    if (message.role === "assistant") {
      return {
        ...base,
        role: "assistant",
        content: message.parts.map((part) =>
          part.type === "reasoning"
            ? { type: "reasoning", text: part.content }
            : { type: "text", text: part.content }
        ),
        status: { type: "complete", reason: "stop" },
        metadata: {
          ...base.metadata,
          unstable_state: null,
          unstable_annotations: [],
          unstable_data: [],
          steps: [],
          custom: {
            sources: message.sources ?? [],
            references: message.references ?? [],
          },
        },
      }
    }

    return {
      ...base,
      role: "user",
      content: message.parts.map((part) => ({
        type: "text",
        text: part.content,
      })),
      attachments: [],
    }
  })
}
