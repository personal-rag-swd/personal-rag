import * as React from "react"
import {
  HttpAgent,
  type HttpAgentConfig,
  type RunAgentParameters,
} from "@ag-ui/client"
import { AssistantRuntimeProvider } from "@assistant-ui/react"
import { useAgUiRuntime } from "@assistant-ui/react-ag-ui"
import type { ThreadHistoryAdapter } from "@assistant-ui/core"
import { toast } from "sonner"
import { formatDistanceToNow } from "date-fns"

import { QuotaBanner } from "@/features/billing/components/QuotaBanner"
import type { QuotaExceededDetail } from "@/features/billing/types"
import {
  fetchNotebookChatHistory,
  useNotebookDocumentsQuery,
} from "@/features/notebooks/api"
import { Thread } from "@/components/assistant-ui/thread"

type CredentialedHttpAgentConfig = HttpAgentConfig & {
  documentIdsRef: React.RefObject<string[]>
}

class CredentialedHttpAgent extends HttpAgent {
  private readonly documentIdsRef: React.RefObject<string[]>

  constructor({ documentIdsRef, ...config }: CredentialedHttpAgentConfig) {
    super(config)
    this.documentIdsRef = documentIdsRef
  }

  protected requestInit(input: Parameters<HttpAgent["run"]>[0]): RequestInit {
    const init = super.requestInit(input)
    return {
      ...init,
      credentials: "include",
    }
  }

  protected prepareRunAgentInput(parameters?: RunAgentParameters) {
    const input = super.prepareRunAgentInput(parameters)
    const documentIds = this.documentIdsRef.current
    if (!documentIds.length) return input
    return {
      ...input,
      forwardedProps: {
        ...input.forwardedProps,
        documentIds,
      },
    }
  }
}

export function ChatPanel({ notebookId }: { notebookId: string }) {
  const apiBaseUrl = import.meta.env.VITE_API_URL

  const [quotaExceeded, setQuotaExceeded] = React.useState<QuotaExceededDetail | null>(
    null
  )

  const quotaAwareFetch = React.useMemo(
    () =>
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const response = await window.fetch(input, init)
        if (response.ok) {
          setQuotaExceeded(null)
        } else if (response.status === 402) {
          try {
            const body = await response.clone().json()
            const detail = body?.detail as QuotaExceededDetail | undefined
            if (detail?.message) {
              setQuotaExceeded(detail)
              toast.error(detail.message, {
                description: detail.reset_at
                  ? `Try again ${formatDistanceToNow(new Date(detail.reset_at), { addSuffix: true })}.`
                  : undefined,
              })
            }
          } catch {
            // Response body wasn't JSON — nothing to surface.
          }
        }
        return response
      },
    []
  )

  const { data: documents } = useNotebookDocumentsQuery(notebookId)
  const indexedDocuments = React.useMemo(
    () =>
      (documents ?? [])
        .filter((document) => document.status === "indexed")
        .map((document) => ({ id: document.id, filename: document.filename })),
    [documents]
  )

  const [scopedDocumentIds, setScopedDocumentIds] = React.useState<string[]>([])
  // Drops any selected document that was deleted or whose indexing is no longer
  // complete, falling back toward "All sources" without a stray effect render.
  const indexedIds = React.useMemo(
    () => new Set(indexedDocuments.map((document) => document.id)),
    [indexedDocuments]
  )
  const effectiveScopedDocumentIds = React.useMemo(
    () => scopedDocumentIds.filter((id) => indexedIds.has(id)),
    [scopedDocumentIds, indexedIds]
  )

  // Mirror the current scope into a ref so the memoized agent can read the
  // latest selection at request time without being rebuilt on every toggle.
  const scopedDocumentIdsRef = React.useRef<string[]>([])
  React.useEffect(() => {
    scopedDocumentIdsRef.current = effectiveScopedDocumentIds
  }, [effectiveScopedDocumentIds])

  const notebookAgent = React.useMemo(
    () =>
      new CredentialedHttpAgent({
        url: apiBaseUrl
          ? `${apiBaseUrl.replace(/\/$/, "")}/api/v1/notebooks/${notebookId}/chat`
          : `/api/v1/notebooks/${notebookId}/chat`,
        agentId: "notebook-chat",
        fetch: quotaAwareFetch,
        documentIdsRef: scopedDocumentIdsRef,
      }),
    [apiBaseUrl, notebookId, quotaAwareFetch]
  )

  const historyAdapter = React.useMemo<ThreadHistoryAdapter>(
    () => ({
      async load() {
        const messages = await fetchNotebookChatHistory(notebookId)
        return {
          headId: messages.at(-1)?.id ?? null,
          messages: messages.map((message, index) => ({
            parentId: index > 0 ? (messages[index - 1]?.id ?? null) : null,
            message,
          })),
        }
      },
      async append() {
        // History persistence is handled by the backend AG-UI endpoint.
      },
    }),
    [notebookId]
  )

  const runtime = useAgUiRuntime({
    agent: notebookAgent,
    adapters: {
      history: historyAdapter,
      threadList: {
        threadId: notebookId,
      },
    },
  })

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <QuotaBanner override={quotaExceeded} />
      <div className="min-h-0 flex-1 overflow-hidden bg-card [&_.aui-thread-root]:bg-card [&_.aui-thread-viewport-footer]:bg-card [&_.aui-thread-welcome-suggestion]:bg-card">
        <AssistantRuntimeProvider runtime={runtime}>
          <Thread
            hideScrollbar
            documentScope={{
              options: indexedDocuments,
              value: effectiveScopedDocumentIds,
              onChange: setScopedDocumentIds,
            }}
          />
        </AssistantRuntimeProvider>
      </div>
    </div>
  )
}
