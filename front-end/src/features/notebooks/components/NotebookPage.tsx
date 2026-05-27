import * as React from "react";
import { useParams, Link } from "react-router-dom";
import {
  PlusIcon,
  ZapIcon,
  FileTextIcon,
  AudioLinesIcon,
  VideoIcon,
  BarChart3Icon,
  BrainCircuitIcon,
  HelpCircleIcon,
  TableIcon,
  SlidersIcon,
  ChevronRightIcon,
  UploadIcon,
  SparklesIcon,
  BookOpenIcon,
  PanelLeftCloseIcon,
  PanelRightCloseIcon,
  Loader2Icon,
  AlertCircleIcon,
  ArrowLeftIcon,
  PencilIcon,
  MoreVerticalIcon,
  Trash2Icon,
  TagIcon,
  MessageSquareIcon,
} from "lucide-react";
import { HttpAgent } from "@ag-ui/client";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useAgUiRuntime } from "@assistant-ui/react-ag-ui";
import type { ThreadHistoryAdapter } from "@assistant-ui/core";

import { fetchNotebookChatHistory, useNotebookQuery } from "@/features/notebooks/api";
import { Thread } from "@/components/assistant-ui/thread";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// ─── Types ──────────────────────────────────────────────────────────────────

type StudioAction = {
  id: string;
  label: string;
  icon: React.ReactNode;
  colorClass: string;
};

class CredentialedHttpAgent extends HttpAgent {
  protected requestInit(input: Parameters<HttpAgent["run"]>[0]): RequestInit {
    const init = super.requestInit(input);
    return {
      ...init,
      credentials: "include",
    };
  }
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STUDIO_ACTIONS: StudioAction[] = [
  {
    id: "audio-overview",
    label: "Audio Overview",
    icon: <AudioLinesIcon className="size-4" />,
    colorClass: "text-amber-500 bg-amber-500/10 border-amber-500/20",
  },
  {
    id: "slide-deck",
    label: "Slide Deck",
    icon: <SlidersIcon className="size-4" />,
    colorClass: "text-lime-500 bg-lime-500/10 border-lime-500/20",
  },
  {
    id: "video-overview",
    label: "Video Overview",
    icon: <VideoIcon className="size-4" />,
    colorClass: "text-sky-500 bg-sky-500/10 border-sky-500/20",
  },
  {
    id: "mind-map",
    label: "Mind Map",
    icon: <BrainCircuitIcon className="size-4" />,
    colorClass: "text-pink-500 bg-pink-500/10 border-pink-500/20",
  },
  {
    id: "reports",
    label: "Reports",
    icon: <BarChart3Icon className="size-4" />,
    colorClass: "text-blue-500 bg-blue-500/10 border-blue-500/20",
  },
  {
    id: "flashcards",
    label: "Flashcards",
    icon: <ZapIcon className="size-4" />,
    colorClass: "text-orange-400 bg-orange-400/10 border-orange-400/20",
  },
  {
    id: "quiz",
    label: "Quiz",
    icon: <HelpCircleIcon className="size-4" />,
    colorClass: "text-violet-500 bg-violet-500/10 border-violet-500/20",
  },
  {
    id: "infographic",
    label: "Infographic",
    icon: <FileTextIcon className="size-4" />,
    colorClass: "text-teal-500 bg-teal-500/10 border-teal-500/20",
  },
  {
    id: "data-table",
    label: "Data Table",
    icon: <TableIcon className="size-4" />,
    colorClass: "text-indigo-500 bg-indigo-500/10 border-indigo-500/20",
  },
];

// ─── Sub-components ──────────────────────────────────────────────────────────

function SourcesPanel() {
  const [searchValue, setSearchValue] = React.useState("");
  const [hasSources] = React.useState(false);

  return (
    <div className="flex flex-col h-full border-r border-border/50 bg-background">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <span className="text-sm font-semibold text-foreground">Sources</span>
        <Tooltip>
          <TooltipTrigger
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            aria-label="Collapse panel"
          >
            <PanelLeftCloseIcon className="size-4" />
          </TooltipTrigger>
          <TooltipContent side="bottom">Collapse panel</TooltipContent>
        </Tooltip>
      </div>

      <div className="flex flex-col gap-3 p-4">
        {/* Add sources button */}
        <Button
          variant="outline"
          className="w-full justify-start gap-2 h-9 rounded-xl border-dashed border-border/80 text-sm font-medium hover:bg-primary/5 hover:border-primary/40 transition-all"
        >
          <PlusIcon className="size-4 text-primary" />
          Add sources
        </Button>

        {/* Search */}
        <div className="relative">
          <Input
            placeholder="Search the web for new sources"
            className="pr-8 h-9 text-xs rounded-xl border-border/60 bg-muted/30"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
          />
        </div>
      </div>

      {/* Sources list or empty state */}
      <ScrollArea className="flex-1">
        {hasSources ? (
          <div className="px-4 pb-4 flex flex-col gap-2">
            {/* Source items would go here */}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center text-center px-6 pt-12 pb-8 gap-3">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-muted/50 text-muted-foreground">
              <BookOpenIcon className="size-5" />
            </div>
            <div className="space-y-1.5">
              <p className="text-sm font-medium text-foreground">
                Saved sources will appear here
              </p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Click Add source above to add PDFs, websites, text, videos, or
                audio files. Or import a file directly from Google Drive.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-2 rounded-xl gap-1.5 text-xs border-border/60 hover:bg-primary/5"
            >
              <UploadIcon className="size-3.5" />
              Import file
            </Button>
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function ChatPanel({ notebookId }: { notebookId: string }) {
  const apiBaseUrl = import.meta.env.VITE_API_URL;
  const notebookAgent = React.useMemo(
    () =>
      new CredentialedHttpAgent({
        url: apiBaseUrl
          ? `${apiBaseUrl.replace(/\/$/, "")}/api/v1/notebooks/${notebookId}/chat`
          : `/api/v1/notebooks/${notebookId}/chat`,
        agentId: "notebook-chat",
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
    <div className="flex flex-col h-full bg-background/50">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <span className="text-sm font-semibold text-foreground">Chat</span>
        <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-foreground">
          <MoreVerticalIcon className="size-4" />
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <AssistantRuntimeProvider runtime={runtime}>
          <Thread hideScrollbar />
        </AssistantRuntimeProvider>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function StudioPanel() {
  return (
    <div className="flex flex-col h-full border-l border-border/50 bg-background">
      {/* Panel header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <span className="text-sm font-semibold text-foreground">Studio</span>
        <Tooltip>
          <TooltipTrigger
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            aria-label="Collapse panel"
          >
            <PanelRightCloseIcon className="size-4" />
          </TooltipTrigger>
          <TooltipContent side="bottom">Collapse panel</TooltipContent>
        </Tooltip>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4">
          {/* Action cards grid */}
          <div className="grid grid-cols-2 gap-2">
            {STUDIO_ACTIONS.map((action) => (
              <button
                key={action.id}
                className="group flex w-full items-center gap-2.5 p-3 rounded-xl border border-border/50 bg-card hover:bg-muted/40 hover:border-primary/20 transition-all duration-200 text-left"
              >
                <div
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-lg border",
                    action.colorClass
                  )}
                >
                  {action.icon}
                </div>
                <span className="min-w-0 flex-1 text-xs font-medium leading-tight text-foreground whitespace-normal wrap-break-word line-clamp-2">
                  {action.label}
                </span>
                <ChevronRightIcon className="size-3 shrink-0 self-center text-muted-foreground mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            ))}
          </div>
        </div>
      </ScrollArea>

      {/* Studio output placeholder */}
      <div className="px-4 pb-4 pt-2 border-t border-border/40">
        <div className="flex flex-col items-center text-center gap-2 py-4">
          <div className="flex size-8 items-center justify-center rounded-xl bg-muted/50 text-muted-foreground">
            <SparklesIcon className="size-4" />
          </div>
          <p className="text-xs font-medium text-foreground">
            Studio output will be saved here.
          </p>
          <p className="text-[11px] text-muted-foreground leading-relaxed max-w-45">
            After adding sources, click to add Audio Overview, Study Guide, Mind Map, and more!
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="w-full rounded-xl gap-1.5 text-xs border-border/60 hover:bg-primary/5 hover:border-primary/30 mt-1"
        >
          <PlusIcon className="size-3.5" />
          Add note
        </Button>
      </div>
    </div>
  );
}

// ─── Notebook Header ──────────────────────────────────────────────────────────

function NotebookHeader({
  name,
  tags,
  documentCount,
  queryCount,
}: {
  name: string;
  tags: string[];
  documentCount: number;
  queryCount: number;
}) {
  return (
    <div className="flex h-(--header-height,48px) shrink-0 items-center gap-3 border-b border-border/50 px-4 bg-background">
      <Link
        to="/dashboard"
        className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors text-xs font-medium"
      >
        <ArrowLeftIcon className="size-3.5" />
        <span>Notebooks</span>
      </Link>

      <Separator orientation="vertical" className="h-4" />

      <div className="flex min-w-0 flex-1 items-center gap-2">
        <div className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <BookOpenIcon className="size-3.5" />
        </div>
        <span className="text-sm font-semibold text-foreground truncate">{name}</span>
        {tags.length > 0 && (
          <div className="hidden sm:flex items-center gap-1 ml-1">
            {tags.slice(0, 2).map((tag) => (
              <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0 h-5">
                <TagIcon className="size-2.5 mr-1" />
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="hidden md:flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <FileTextIcon className="size-3" />
          <strong className="font-semibold text-foreground">{documentCount}</strong> docs
        </span>
        <span className="flex items-center gap-1">
          <MessageSquareIcon className="size-3" />
          <strong className="font-semibold text-foreground">{queryCount}</strong> queries
        </span>
      </div>

      <div className="flex items-center gap-1 ml-2">
        <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-foreground">
          <PencilIcon className="size-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-destructive">
          <Trash2Icon className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ─── Error / Loading states ───────────────────────────────────────────────────

function NotebookSkeleton() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex h-12 items-center gap-3 border-b border-border/50 px-4">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-px" />
        <Skeleton className="h-5 w-48" />
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="w-64 border-r border-border/50 p-4 flex flex-col gap-3">
          <Skeleton className="h-9 w-full rounded-xl" />
          <Skeleton className="h-9 w-full rounded-xl" />
          <Skeleton className="h-7 w-24 rounded-full" />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2Icon className="size-5 animate-spin" />
            <span className="text-sm">Loading notebook...</span>
          </div>
        </div>
        <div className="w-64 border-l border-border/50 p-4 flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}

function NotebookError({ message }: { message: string }) {
  return (
    <div className="flex flex-col h-full items-center justify-center gap-4 text-center px-6">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertCircleIcon className="size-7" />
      </div>
      <div className="space-y-1.5">
        <h3 className="text-base font-bold text-foreground">Notebook not found</h3>
        <p className="text-sm text-muted-foreground max-w-xs">{message}</p>
      </div>
      <Link
        to="/dashboard"
        className="mt-2 inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
      >
        <ArrowLeftIcon className="size-4" />
        Back to Notebooks
      </Link>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function NotebookPage() {
  const { id } = useParams();
  const { data: notebook, isLoading, isError, error } = useNotebookQuery(id);

  if (!id) {
    return <NotebookError message="This notebook could not be loaded. It may have been deleted or you don't have access." />;
  }

  if (isLoading) {
    return <NotebookSkeleton />;
  }

  if (isError || !notebook) {
    return (
      <NotebookError
        message={
          error instanceof Error
            ? error.message
            : "This notebook could not be loaded. It may have been deleted or you don't have access."
        }
      />
    );
  }

  return (
    <div className="flex flex-col h-full animate-in fade-in duration-300">
      {/* Top bar with notebook info */}
      <NotebookHeader
        name={notebook.name}
        tags={notebook.tags}
        documentCount={notebook.documentCount}
        queryCount={notebook.queryCount}
      />

      {/* Three-column layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sources — left */}
        <div className="w-1/4 shrink-0 overflow-hidden">
          <SourcesPanel />
        </div>

        {/* Chat — center */}
        <div className="w-1/2 min-w-0 overflow-hidden">
          <ChatPanel notebookId={id} />
        </div>

        {/* Studio — right */}
        <div className="w-1/4 shrink-0 overflow-hidden">
          <StudioPanel />
        </div>
      </div>
    </div>
  );
}
