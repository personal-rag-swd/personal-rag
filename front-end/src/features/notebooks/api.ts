import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { create } from "zustand"
import type { ThreadMessage } from "@assistant-ui/core"
import { apiClient, apiFetch } from "@/lib/api-client"
import {
  type Notebook,
  type NotebookApiPayload,
  type NotebookDocument,
  type NotebookDocumentApiPayload,
  type NotebookDocumentEvent,
  type NotebookReport,
  type NotebookReportApiPayload,
  type MindMapContent,
  type MindMapContentApiPayload,
  type MindMapNode,
  type MindMapNodeApiPayload,
  type ReportType,
  type ReportStatus,
} from "./types"

export type NotebookDocumentPreview = {
  filename: string
  contentType: string | null
  size: number | null
  url: string | null
  content: string | null
  previewType: "url" | "text"
}

type NotebookDocumentPreviewApiPayload = {
  filename: string
  content_type: string | null
  size: number | null
  url: string | null
  content: string | null
  preview_type: "url" | "text"
}

export function buildApiUrl(path: string): string {
  const base = import.meta.env.VITE_API_URL
  if (!base || base === "/") {
    return path
  }
  const normalizedBase = base.endsWith("/") ? base : `${base}/`
  return new URL(path.replace(/^\//, ""), normalizedBase).toString()
}

function mapNotebookReport(payload: NotebookReportApiPayload): NotebookReport {
  const base = {
    id: payload.id,
    notebookId: payload.notebook_id,
    status: payload.status as ReportStatus,
    errorMessage: payload.error_message ?? null,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  }

  switch (payload.report_type) {
    case "mindmap":
      return {
        ...base,
        reportType: "mindmap",
        content: mapMindMapContent(payload.content),
      }
    case "briefing":
      return {
        ...base,
        reportType: "briefing",
        content: payload.content,
      }
    case "study_guide":
      return {
        ...base,
        reportType: "study_guide",
        content: payload.content,
      }
    case "blog":
      return {
        ...base,
        reportType: "blog",
        content: payload.content,
      }
    case "custom":
      return {
        ...base,
        reportType: "custom",
        content: payload.content,
      }
    case "quiz":
      return {
        ...base,
        reportType: "quiz",
        content: payload.content,
      }
    case "flashcards":
      return {
        ...base,
        reportType: "flashcards",
        content: payload.content,
      }
    case "note":
      return {
        ...base,
        reportType: "note",
        content: payload.content,
      }
  }
}

function mapMindMapContent(content: MindMapContentApiPayload): MindMapContent {
  return {
    central_topic: content.central_topic ?? "",
    nodes: (content.nodes ?? []).map(mapMindMapNode),
    relationships: content.relationships ?? [],
  }
}

function mapMindMapNode(node: MindMapNodeApiPayload): MindMapNode {
  return {
    id: node.id,
    label: node.label,
    type: node.type,
    parentId: node.parentId ?? node.parent_id ?? null,
    description: node.description ?? null,
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

function mapNotebookDocumentPreview(
  payload: NotebookDocumentPreviewApiPayload
): NotebookDocumentPreview {
  return {
    filename: payload.filename,
    contentType: payload.content_type,
    size: payload.size,
    url: payload.url,
    content: payload.content,
    previewType: payload.preview_type,
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

let eventSource: EventSource | null = null
let refCount = 0
const listeners = new Set<(event: MessageEvent) => void>()
let disconnectTimeout: ReturnType<typeof setTimeout> | null = null

export const useNotebookEventsStore = create<{
  health: NotebookDocumentEventsHealth
}>(() => ({
  health: "idle",
}))

function connect() {
  if (eventSource || typeof EventSource === "undefined") {
    return
  }

  if (disconnectTimeout) {
    clearTimeout(disconnectTimeout)
    disconnectTimeout = null
  }

  useNotebookEventsStore.setState({ health: "connected" })

  const url = buildApiUrl("/api/v1/notebooks/events")
  const s = new EventSource(url, { withCredentials: true })
  eventSource = s

  let hasConnected = false

  s.onopen = () => {
    hasConnected = true
    useNotebookEventsStore.setState({ health: "connected" })
    console.info("[notebook-events] connected to centralized event source")
  }

  s.onmessage = (event) => {
    listeners.forEach((listener) => listener(event))
  }

  s.onerror = () => {
    const currentHealth = hasConnected ? "reconnecting" : "failed"
    useNotebookEventsStore.setState({ health: currentHealth })
    console.warn(
      `[notebook-events] centralized event source error: ${currentHealth}`
    )
  }
}

function disconnect() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
    useNotebookEventsStore.setState({ health: "idle" })
    console.info("[notebook-events] disconnected centralized event source")
  }
}

export function subscribeToNotebookEvents(
  listener: (event: MessageEvent) => void
): () => void {
  listeners.add(listener)
  refCount++

  if (refCount === 1) {
    connect()
  }

  return () => {
    listeners.delete(listener)
    refCount--

    if (refCount === 0) {
      if (disconnectTimeout) {
        clearTimeout(disconnectTimeout)
      }
      if (typeof window !== "undefined") {
        disconnectTimeout = setTimeout(() => {
          if (refCount === 0) {
            disconnect()
          }
        }, 2000)
      } else {
        disconnect()
      }
    }
  }
}

export function useNotebookDocumentEvents(notebookId: string | undefined) {
  const queryClient = useQueryClient()
  const health = useNotebookEventsStore((state) => state.health)
  const [isVisible, setIsVisible] = useState(
    typeof document === "undefined"
      ? true
      : document.visibilityState === "visible"
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

    const handleMessage = (event: MessageEvent) => {
      try {
        const payload: NotebookDocumentEvent = JSON.parse(event.data)
        if (payload.type === "snapshot") {
          if (payload.notebook_id === notebookId) {
            queryClient.setQueryData(
              ["notebooks", notebookId, "documents"],
              payload.documents.map(mapNotebookDocument)
            )
          }
          return
        }
        if (payload.type === "document_update") {
          if (payload.notebook_id === notebookId) {
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
          return
        }
        if (payload.type === "report_snapshot") {
          if (payload.notebook_id === notebookId) {
            queryClient.setQueryData(
              ["notebooks", notebookId, "reports"],
              payload.reports.map(mapNotebookReport)
            )
          }
          return
        }
        if (payload.type === "report_update") {
          if (payload.notebook_id === notebookId) {
            queryClient.setQueryData<NotebookReport[]>(
              ["notebooks", notebookId, "reports"],
              (current = []) => {
                const nextReport = mapNotebookReport(payload.report)
                const existingIndex = current.findIndex(
                  (report) => report.id === nextReport.id
                )
                if (existingIndex === -1) {
                  return [nextReport, ...current]
                }
                const next = [...current]
                next[existingIndex] = nextReport
                return next
              }
            )
          }
        }
      } catch (error) {
        console.warn(
          `[notebook-doc-events] failed to parse event notebook=${notebookId}`,
          error
        )
      }
    }

    const unsubscribe = subscribeToNotebookEvents(handleMessage)
    return () => {
      unsubscribe()
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
      void queryClient.invalidateQueries({
        queryKey: ["notebooks", variables.notebookId, "reports"],
      })
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] })
    },
  })
}

export async function getNotebookDocumentPreview(
  notebookId: string,
  documentId: string
) {
  const data = await apiFetch<NotebookDocumentPreviewApiPayload>(
    `/api/v1/notebooks/${notebookId}/documents/${documentId}/preview`
  )
  return mapNotebookDocumentPreview(data)
}

export async function getNotebookDocumentDownloadBlob(
  notebookId: string,
  documentId: string
) {
  const response = await apiClient.request<Blob>({
    url: `/api/v1/notebooks/${notebookId}/documents/${documentId}/download`,
    responseType: "blob",
  })
  return response.data
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
    {
      reportType: ReportType
      additionalInstructions?: string
      detailLevel?: string
      numberOfQuestions?: string
      numberOfCards?: string
    }
  >({
    mutationFn: async ({
      reportType,
      additionalInstructions,
      detailLevel,
      numberOfQuestions,
      numberOfCards,
    }) => {
      const data = await apiFetch<NotebookReportApiPayload>(
        `/api/v1/notebooks/${notebookId}/reports`,
        {
          method: "POST",
          data: {
            report_type: reportType,
            additional_instructions: additionalInstructions,
            detail_level: detailLevel,
            number_of_questions: numberOfQuestions,
            number_of_cards: numberOfCards,
          },
        }
      )
      return mapNotebookReport(data)
    },
    onSuccess: (report) => {
      queryClient.setQueryData<NotebookReport[]>(
        ["notebooks", notebookId, "reports"],
        (current = []) => {
          if (current.some((r) => r.id === report.id)) {
            return current
          }
          return [report, ...current]
        }
      )
    },
  })
}

export function useCancelNotebookReportMutation(
  notebookId: string,
  reportId: string
) {
  const queryClient = useQueryClient()
  return useMutation<void, Error>({
    mutationFn: async () => {
      await apiFetch(
        `/api/v1/notebooks/${notebookId}/reports/${reportId}/cancel`,
        { method: "POST" }
      )
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["notebooks", notebookId, "reports"],
      })
    },
  })
}

export function useDeleteNotebookReportMutation(
  notebookId: string,
  reportId: string
) {
  const queryClient = useQueryClient()
  return useMutation<void, Error>({
    mutationFn: async () => {
      await apiFetch(`/api/v1/notebooks/${notebookId}/reports/${reportId}`, {
        method: "DELETE",
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["notebooks", notebookId, "reports"],
      })
      void queryClient.invalidateQueries({
        queryKey: ["notebooks", notebookId, "documents"],
      })
      void queryClient.invalidateQueries({ queryKey: ["notebooks"] })
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
              status: { type: "complete" as const },
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
