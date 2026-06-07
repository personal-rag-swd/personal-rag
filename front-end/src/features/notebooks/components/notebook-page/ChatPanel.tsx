import * as React from "react";
import { HttpAgent } from "@ag-ui/client";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useAgUiRuntime } from "@assistant-ui/react-ag-ui";
import type { ThreadHistoryAdapter } from "@assistant-ui/core";

import { fetchNotebookChatHistory } from "@/features/notebooks/api";
import { Thread } from "@/components/assistant-ui/thread";

class CredentialedHttpAgent extends HttpAgent {
  protected requestInit(input: Parameters<HttpAgent["run"]>[0]): RequestInit {
    const init = super.requestInit(input);
    return {
      ...init,
      credentials: "include",
    };
  }
}

export function ChatPanel({ notebookId }: { notebookId: string }) {
  const apiBaseUrl = import.meta.env.VITE_API_URL;

  const notebookAgent = React.useMemo(
    () =>
      new CredentialedHttpAgent({
        url: apiBaseUrl
          ? `${apiBaseUrl.replace(/\/$/, "")}/api/v1/notebooks/${notebookId}/chat`
          : `/api/v1/notebooks/${notebookId}/chat`,
        agentId: "notebook-chat",
        fetch: window.fetch.bind(window),
      }),
    [apiBaseUrl, notebookId]
  );
  const historyAdapter = React.useMemo<ThreadHistoryAdapter>(
    () => ({
      async load() {
        const messages = await fetchNotebookChatHistory(notebookId);
        return {
          headId: messages.at(-1)?.id ?? null,
          messages: messages.map((message, index) => ({
            parentId: index > 0 ? messages[index - 1]?.id ?? null : null,
            message,
          })),
        };
      },
      async append() {
        // History persistence is handled by the backend AG-UI endpoint.
      },
    }),
    [notebookId]
  );

  const runtime = useAgUiRuntime({
    agent: notebookAgent,
    adapters: {
      history: historyAdapter,
      threadList: {
        threadId: notebookId,
      },
    },
  });

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <div className="min-h-0 flex-1 overflow-hidden bg-card [&_.aui-thread-root]:bg-card [&_.aui-thread-viewport-footer]:bg-card [&_.aui-thread-welcome-suggestion]:bg-card">
        <AssistantRuntimeProvider runtime={runtime}>
          <Thread hideScrollbar />
        </AssistantRuntimeProvider>
      </div>
    </div>
  );
}
