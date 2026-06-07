import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import type { ThreadMessage } from "@assistant-ui/core"
import { apiFetch } from "@/lib/api-client"
import {
  type Notebook,
  type NotebookApiPayload,
  type NotebookPopulateApiPayload,
  type NotebookDocument,
  type NotebookDocumentApiPayload,
  type NotebookDocumentEvent,
  type NotebookReport,
  type NotebookReportApiPayload,
  type MindMapContent,
  type MindMapContentApiPayload,
  type MindMapNodeApiPayload,
  type ReportContent,
  type ReportType,
} from "./types"

function buildApiUrl(path: string): string {
  const base = import.meta.env.VITE_API_URL
  if (!base || base === "/") {
    return path
  }
  const normalizedBase = base.endsWith("/") ? base : `${base}/`
  return new URL(path.replace(/^\//, ""), normalizedBase).toString()
}

function mapNotebookReport(payload: NotebookReportApiPayload): NotebookReport {
  return {
    id: payload.id,
    notebookId: payload.notebook_id,
    reportType: payload.report_type,
    content:
      payload.report_type === "mindmap"
        ? mapMindMapContent(payload.content)
        : (payload.content as ReportContent),
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  }
}

function mapMindMapContent(content: NotebookReportApiPayload["content"]): MindMapContent {
  if (!isMindMapContentPayload(content)) {
    return {
      central_topic: "Mind map",
      nodes: [],
      relationships: [],
    }
  }

  return {
    central_topic: content.central_topic,
    nodes: content.nodes.map(mapMindMapNode),
    relationships: content.relationships ?? [],
  }
}

function mapMindMapNode(node: MindMapNodeApiPayload) {
  return {
    id: node.id,
    label: node.label,
    type: node.type,
    parentId: node.parentId ?? node.parent_id ?? null,
    description: node.description ?? null,
  }
}

function isMindMapContentPayload(
  content: ReportContent | NotebookReportApiPayload["content"]
): content is MindMapContentApiPayload {
  return Boolean(
    content &&
      typeof content === "object" &&
      "nodes" in content &&
      Array.isArray(content.nodes)
  )
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

export type NotebookDocumentEventsHealth =
  | "idle"
  | "connected"
  | "reconnecting"
  | "failed"

export function useNotebookDocumentEvents(notebookId: string | undefined) {
  const queryClient = useQueryClient()
  const [health, setHealth] = useState<NotebookDocumentEventsHealth>("idle")
  const [isVisible, setIsVisible] = useState(
    typeof document === "undefined" ? true : document.visibilityState === "visible"
  )

  useEffect(() => {
    const onVisibilityChange = () => {
      setIsVisible(document.visibilityState === "visible")
    }
    document.addEventListener("visibilitychange", onVisibilityChange)
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange)
    }
  }, [])

  useEffect(() => {
    if (!notebookId || !isVisible) {
      return
    }

    let hasConnected = false
    const source = new EventSource(
      buildApiUrl(`/api/v1/notebooks/${notebookId}/documents/events`)
    )

    source.onopen = () => {
      hasConnected = true
      setHealth("connected")
      console.info(
        `[notebook-doc-events] connected notebook=${notebookId}`
      )
    }

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as NotebookDocumentEvent
        if (payload.type === "snapshot") {
          queryClient.setQueryData(
            ["notebooks", notebookId, "documents"],
            payload.documents.map(mapNotebookDocument)
          )
          return
        }
        if (payload.type === "document_update") {
          queryClient.setQueryData<NotebookDocument[]>(
            ["notebooks", notebookId, "documents"],
            (current = []) => {
              const nextDocument = mapNotebookDocument(payload.document)
              const existingIndex = current.findIndex(
                (document) => document.id === nextDocument.id
              )
              if (existingIndex === -1) {
                return [nextDocument, ...current]
              }
              const next = [...current]
              next[existingIndex] = nextDocument
              return next
            }
          )
        }
      } catch (error) {
        console.warn(
          `[notebook-doc-events] failed to parse event notebook=${notebookId}`,
          error
        )
      }
    }

    source.onerror = () => {
      setHealth(hasConnected ? "reconnecting" : "failed")
      console.warn(
        `[notebook-doc-events] ${hasConnected ? "reconnecting" : "failed"} notebook=${notebookId}`
      )
    }

    return () => {
      source.close()
      console.info(
        `[notebook-doc-events] disconnected notebook=${notebookId}`
      )
    }
  }, [isVisible, notebookId, queryClient])

  if (!notebookId || !isVisible) {
    return "idle"
  }
  return health
}

export function useNotebookDocumentsQuery(
  notebookId: string | undefined,
  streamHealth: NotebookDocumentEventsHealth = "idle"
) {
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
      if (streamHealth === "connected") {
        return 30000
      }
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
  parts: {
    type: "text" | "reasoning" | "tool-call"
    content?: string
    toolCallId?: string
    toolName?: string
    argsText?: string
    result?: unknown
  }[]
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
    { reportType: ReportType; additionalInstructions?: string; detailLevel?: string }
  >({
    mutationFn: async ({ reportType, additionalInstructions, detailLevel }) => {
      const data = await apiFetch<NotebookReportApiPayload>(
        `/api/v1/notebooks/${notebookId}/reports`,
        {
          method: "POST",
          data: {
            report_type: reportType,
            additional_instructions: additionalInstructions,
            detail_level: detailLevel,
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
        content: message.parts.map((part) => {
          if (part.type === "reasoning") {
            return { type: "reasoning" as const, text: part.content ?? "" }
          }
          if (part.type === "tool-call") {
            return {
              type: "tool-call" as const,
              toolCallId: part.toolCallId ?? "",
              toolName: part.toolName ?? "",
              argsText: part.argsText ?? "",
              args: (() => {
                try {
                  return part.argsText ? JSON.parse(part.argsText) : {}
                } catch {
                  return {}
                }
              })(),
              result: part.result,
              status: { type: "complete" as const }
            }
          }
          return { type: "text" as const, text: part.content ?? "" }
        }),
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
        type: "text" as const,
        text: part.content ?? "",
      })),
      attachments: [],
    }
  })
}
