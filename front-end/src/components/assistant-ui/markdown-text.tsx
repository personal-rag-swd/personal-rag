"use client"

import "@assistant-ui/react-markdown/styles/dot.css"

import {
  type CodeHeaderProps,
  MarkdownTextPrimitive,
  unstable_memoizeMarkdownComponents as memoizeMarkdownComponents,
  useIsMarkdownCodeBlock,
} from "@assistant-ui/react-markdown"
import remarkGfm from "remark-gfm"
import { type FC, memo, useState, useEffect, useRef } from "react"
import {
  CheckIcon,
  CopyIcon,
  Loader2Icon,
  ExternalLinkIcon,
} from "lucide-react"

import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button"
import { cn } from "@/lib/utils"
import { useAuiState } from "@assistant-ui/react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useParams } from "react-router-dom"
import { apiFetch } from "@/lib/api-client"

const preprocessCitations = (text: string) => {
  const citationMap = new Map<string, number>()
  let currentNum = 1
  const regex =
    /\[(?:file=([^,\]]+)|([^,\]]+)),\s*(?:doc_id=([^,\]]+),\s*)?chunk(?:=|\s+)(\d+)(?:\s*,\s*doc_id=([^,\]]+))?\]/g

  return text.replace(
    regex,
    (_match, filenameKv, filenameLegacy, docId1, chunkIndex, docId2) => {
      const filename = (filenameKv ?? filenameLegacy ?? "").trim()
      const docId = (docId1 ?? docId2 ?? "").trim()
      const key = docId ? `${docId}:${chunkIndex}` : `${filename}:${chunkIndex}`
      let num = citationMap.get(key)
      if (num === undefined) {
        num = currentNum++
        citationMap.set(key, num)
      }
      const docIdPart = docId ? `/${encodeURIComponent(docId)}` : ""
      return `[${num}](#cite/${num}/${encodeURIComponent(filename)}/${chunkIndex}${docIdPart})`
    }
  )
}

const MarkdownTextImpl = () => {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      className="aui-md"
      components={defaultComponents}
      preprocess={preprocessCitations}
    />
  )
}

export const MarkdownText = memo(MarkdownTextImpl)

interface ChunkType {
  id?: string
  filename: string
  document_id: string
  chunk_index: number
  content: string
  metadata?: Record<string, unknown>
}

interface ReferenceType {
  ref_id: string
  citation_number: number
  filename: string
  document_id: string
  chunk_index: number
  content: string
}

function DocumentChunksViewer({
  documentId,
  notebookId,
  activeChunkIndex,
}: {
  documentId: string
  notebookId: string | undefined
  activeChunkIndex: number
}) {
  const [chunks, setChunks] = useState<ChunkType[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const activeChunkRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!notebookId || !documentId) return

    Promise.resolve().then(() => {
      setIsLoading(true)
      setError(null)
    })

    apiFetch<ChunkType[]>(
      `/api/v1/notebooks/${notebookId}/documents/${documentId}/chunks`
    )
      .then((data) => {
        setChunks(data)
      })
      .catch((err: Error) => {
        console.error(err)
        setError(err.message || "Could not load document content.")
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [documentId, notebookId])

  useEffect(() => {
    if (chunks.length > 0 && activeChunkRef.current) {
      const timer = setTimeout(() => {
        activeChunkRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        })
      }, 300)
      return () => clearTimeout(timer)
    }
  }, [chunks, activeChunkIndex])

  if (isLoading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3">
        <Loader2Icon className="size-6 animate-spin text-primary" />
        <p className="animate-pulse text-xs font-medium text-muted-foreground">
          Loading full document content...
        </p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center p-6 text-center">
        <p className="max-w-sm rounded-xl border border-destructive/10 bg-destructive/5 px-4 py-3 text-xs text-destructive">
          {error}
        </p>
      </div>
    )
  }

  return (
    <ScrollArea className="h-full w-full">
      <div className="mx-auto max-w-2xl space-y-6 px-6 py-8">
        {chunks.map((chunk) => {
          const isActive = chunk.chunk_index === activeChunkIndex
          return (
            <div
              key={chunk.id}
              ref={isActive ? activeChunkRef : undefined}
              className={cn(
                "rounded-2xl border border-transparent p-4 text-sm leading-relaxed break-words whitespace-pre-wrap text-foreground/80 transition-all duration-300",
                isActive
                  ? "border-blue-500/20 bg-blue-500/5 font-medium text-foreground shadow-xs ring-1 ring-blue-500/20"
                  : "hover:bg-muted/10"
              )}
            >
              {chunk.content}
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}

function CitationPopover({
  citationNumber,
  filename,
  chunkIndex,
  documentId,
}: {
  citationNumber: string
  filename?: string
  chunkIndex?: number
  documentId?: string
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [isViewerOpen, setIsViewerOpen] = useState(false)

  const { id: notebookId } = useParams()
  const sourcesRaw = useAuiState(
    (s) =>
      (
        (s.message.metadata as Record<string, unknown> | undefined)?.custom as
          | Record<string, unknown>
          | undefined
      )?.sources as ChunkType[] | undefined
  )
  const sources = sourcesRaw ?? []
  const referencesRaw = useAuiState(
    (s) =>
      (
        (s.message.metadata as Record<string, unknown> | undefined)?.custom as
          | Record<string, unknown>
          | undefined
      )?.references as ReferenceType[] | undefined
  )
  const references = referencesRaw ?? []
  const citationNumberInt = Number.parseInt(citationNumber, 10)
  const localReference = references.find(
    (ref) => ref.citation_number === citationNumberInt
  )
  const resolvedFilename = localReference?.filename ?? filename ?? ""
  const resolvedDocumentId = localReference?.document_id ?? documentId ?? ""
  const resolvedChunkIndex = localReference?.chunk_index ?? chunkIndex ?? -1

  const localSource = sources.find((src) => {
    if (resolvedDocumentId) {
      return (
        src.document_id === resolvedDocumentId &&
        src.chunk_index === resolvedChunkIndex
      )
    }
    if (!resolvedFilename || resolvedChunkIndex < 0) return false
    return (
      src.filename === resolvedFilename &&
      src.chunk_index === resolvedChunkIndex
    )
  })

  const finalDocumentId = resolvedDocumentId || localSource?.document_id || ""

  const [fetchedSource, setFetchedSource] = useState<ChunkType | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (localReference || localSource || !isOpen || !notebookId) return
    if (resolvedChunkIndex < 0) return

    Promise.resolve().then(() => {
      setIsLoading(true)
    })

    const fetchPromise = finalDocumentId
      ? apiFetch<ChunkType>(
          `/api/v1/notebooks/${notebookId}/documents/${finalDocumentId}/chunks/${resolvedChunkIndex}`
        )
      : resolvedFilename
        ? apiFetch<{ content: string; filename: string; chunk_index: number }>(
            `/api/v1/notebooks/${notebookId}/chunks?filename=${encodeURIComponent(resolvedFilename)}&chunk_index=${resolvedChunkIndex}`
          ).then((data) => ({
            filename: data.filename,
            document_id: "",
            chunk_index: data.chunk_index,
            content: data.content,
          }))
        : Promise.reject(new Error("Missing source lookup metadata"))

    fetchPromise
      .then((data) => {
        setFetchedSource(data)
      })
      .catch((err: Error) => {
        console.error(err)
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [
    localReference,
    localSource,
    finalDocumentId,
    resolvedChunkIndex,
    resolvedFilename,
    notebookId,
    isOpen,
  ])

  const activeSource = localReference || localSource || fetchedSource
  const contentText = activeSource?.content ?? ""

  const lines = contentText
    .split("\n")
    .map((l: string) => l.trim())
    .filter(Boolean)
  const subtitle = lines[0] && lines[0].length < 80 ? lines[0] : ""
  const bodyText = subtitle ? lines.slice(1).join("\n") : contentText

  return (
    <>
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger
          render={
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                setIsOpen(!isOpen)
              }}
              className="mx-0.5 inline-flex size-5 cursor-pointer items-center justify-center rounded-full bg-blue-500/10 align-super text-[10px] font-semibold text-blue-600 transition-all hover:scale-105 hover:bg-blue-500/20 active:scale-95 dark:bg-blue-500/20 dark:text-blue-400"
              aria-label={`Source citation ${citationNumber}`}
            >
              {citationNumber}
            </button>
          }
        />
        <PopoverContent className="w-80 overflow-hidden rounded-2xl border border-border/80 bg-popover p-0 shadow-xl select-none">
          <div className="flex items-center justify-between border-b border-border/40 bg-muted/20 px-3.5 py-2.5">
            <span
              className="max-w-[80%] truncate text-xs font-semibold text-foreground/90"
              title={resolvedFilename}
            >
              {resolvedFilename}
            </span>
          </div>

          <div className="max-h-48 [scrollbar-width:none] overflow-y-auto p-3.5 text-xs leading-relaxed text-muted-foreground [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 py-6 text-muted-foreground">
                <Loader2Icon className="size-3.5 animate-spin text-primary" />
                <span>Loading source...</span>
              </div>
            ) : contentText ? (
              <div className="space-y-2">
                {subtitle && (
                  <h4 className="leading-snug font-semibold text-foreground/90">
                    {subtitle}
                  </h4>
                )}
                <p className="text-[11px] leading-relaxed break-words whitespace-pre-wrap">
                  {bodyText}
                </p>
              </div>
            ) : (
              <p className="py-2 text-center text-muted-foreground/60 italic">
                Source content unavailable.
              </p>
            )}
          </div>

          <div className="flex justify-end border-t border-border/40 bg-muted/10 px-3.5 py-2.5">
            <button
              type="button"
              disabled={!finalDocumentId || resolvedChunkIndex < 0}
              onClick={() => {
                setIsOpen(false)
                setIsViewerOpen(true)
              }}
              className="inline-flex cursor-pointer items-center gap-1.5 text-[11px] font-semibold text-primary transition-colors hover:text-primary/80 disabled:cursor-not-allowed disabled:text-muted-foreground/50"
            >
              <ExternalLinkIcon className="size-3" />
              View source
            </button>
          </div>
        </PopoverContent>
      </Popover>

      <Dialog open={isViewerOpen} onOpenChange={setIsViewerOpen}>
        <DialogContent className="flex h-[85vh] max-w-3xl flex-col overflow-hidden rounded-3xl border border-border/60 bg-popover p-0 shadow-2xl">
          <div className="flex shrink-0 items-center justify-between border-b border-border/40 bg-muted/10 px-6 py-4">
            <DialogHeader className="gap-0.5">
              <DialogTitle className="max-w-xl truncate text-base font-semibold text-foreground">
                {resolvedFilename}
              </DialogTitle>
            </DialogHeader>
          </div>

          <div className="min-h-0 flex-1 bg-background/50">
            <DocumentChunksViewer
              documentId={finalDocumentId}
              notebookId={notebookId}
              activeChunkIndex={resolvedChunkIndex}
            />
          </div>

          <div className="flex shrink-0 justify-end border-t border-border/40 bg-muted/10 px-6 py-3.5">
            <DialogFooter showCloseButton />
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

const CodeHeader: FC<CodeHeaderProps> = ({ language, code }) => {
  const { isCopied, copyToClipboard } = useCopyToClipboard()
  const onCopy = () => {
    if (!code || isCopied) return
    copyToClipboard(code)
  }

  return (
    <div className="aui-code-header-root mt-2.5 flex items-center justify-between rounded-t-lg border border-b-0 border-border/50 bg-muted/50 px-3 py-1.5 text-xs">
      <span className="aui-code-header-language font-medium text-muted-foreground lowercase">
        {language}
      </span>
      <TooltipIconButton tooltip="Copy" onClick={onCopy}>
        {!isCopied && <CopyIcon />}
        {isCopied && <CheckIcon />}
      </TooltipIconButton>
    </div>
  )
}

const useCopyToClipboard = ({
  copiedDuration = 3000,
}: {
  copiedDuration?: number
} = {}) => {
  const [isCopied, setIsCopied] = useState<boolean>(false)

  const copyToClipboard = (value: string) => {
    if (!value || typeof navigator === "undefined" || !navigator.clipboard) {
      return
    }

    navigator.clipboard.writeText(value).then(
      () => {
        setIsCopied(true)
        setTimeout(() => setIsCopied(false), copiedDuration)
      },
      () => {}
    )
  }

  return { isCopied, copyToClipboard }
}

const defaultComponents = memoizeMarkdownComponents({
  h1: ({ className, ...props }) => (
    <h1
      className={cn(
        "aui-md-h1 mb-2 scroll-m-20 text-base font-semibold first:mt-0 last:mb-0",
        className
      )}
      {...props}
    />
  ),
  h2: ({ className, ...props }) => (
    <h2
      className={cn(
        "aui-md-h2 mt-3 mb-1.5 scroll-m-20 text-sm font-semibold first:mt-0 last:mb-0",
        className
      )}
      {...props}
    />
  ),
  h3: ({ className, ...props }) => (
    <h3
      className={cn(
        "aui-md-h3 mt-2.5 mb-1 scroll-m-20 text-sm font-semibold first:mt-0 last:mb-0",
        className
      )}
      {...props}
    />
  ),
  h4: ({ className, ...props }) => (
    <h4
      className={cn(
        "aui-md-h4 mt-2 mb-1 scroll-m-20 text-sm font-medium first:mt-0 last:mb-0",
        className
      )}
      {...props}
    />
  ),
  h5: ({ className, ...props }) => (
    <h5
      className={cn(
        "aui-md-h5 mt-2 mb-1 text-sm font-medium first:mt-0 last:mb-0",
        className
      )}
      {...props}
    />
  ),
  h6: ({ className, ...props }) => (
    <h6
      className={cn(
        "aui-md-h6 mt-2 mb-1 text-sm font-medium first:mt-0 last:mb-0",
        className
      )}
      {...props}
    />
  ),
  p: ({ className, ...props }) => (
    <p
      className={cn(
        "aui-md-p my-2.5 leading-normal first:mt-0 last:mb-0",
        className
      )}
      {...props}
    />
  ),
  a: ({ href, children, className, ...props }) => {
    if (href && href.startsWith("#cite/")) {
      const parts = href.split("/")
      const numericCitation = Number.parseInt(parts[1], 10)
      const fallbackFilename = parts[2]
        ? decodeURIComponent(parts[2])
        : undefined
      const fallbackChunkIndex = parts[3]
        ? Number.parseInt(parts[3], 10)
        : undefined
      const fallbackDocId = parts[4] ? decodeURIComponent(parts[4]) : undefined
      if (!Number.isNaN(numericCitation)) {
        return (
          <CitationPopover
            citationNumber={String(numericCitation)}
            filename={fallbackFilename}
            chunkIndex={fallbackChunkIndex}
            documentId={fallbackDocId}
          />
        )
      }
      const filename = decodeURIComponent(parts[1])
      const chunkIndex = Number.parseInt(parts[2], 10)
      return (
        <CitationPopover
          filename={filename}
          chunkIndex={chunkIndex}
          citationNumber={String(children)}
        />
      )
    }
    return (
      <a
        className={cn(
          "aui-md-a text-primary underline underline-offset-2 hover:text-primary/80",
          className
        )}
        href={href}
        {...props}
      >
        {children}
      </a>
    )
  },
  blockquote: ({ className, ...props }) => (
    <blockquote
      className={cn(
        "aui-md-blockquote my-2.5 border-s-2 border-muted-foreground/30 ps-3 text-muted-foreground italic",
        className
      )}
      {...props}
    />
  ),
  ul: ({ className, ...props }) => (
    <ul
      className={cn(
        "aui-md-ul my-2 ms-4 list-disc marker:text-muted-foreground [&>li]:mt-1",
        className
      )}
      {...props}
    />
  ),
  ol: ({ className, ...props }) => (
    <ol
      className={cn(
        "aui-md-ol my-2 ms-4 list-decimal marker:text-muted-foreground [&>li]:mt-1",
        className
      )}
      {...props}
    />
  ),
  hr: ({ className, ...props }) => (
    <hr
      className={cn("aui-md-hr my-2 border-muted-foreground/20", className)}
      {...props}
    />
  ),
  table: ({ className, ...props }) => (
    <table
      className={cn(
        "aui-md-table my-2 w-full border-separate border-spacing-0 overflow-y-auto",
        className
      )}
      {...props}
    />
  ),
  th: ({ className, ...props }) => (
    <th
      className={cn(
        "aui-md-th bg-muted px-2 py-1 text-start font-medium first:rounded-ss-lg last:rounded-se-lg [[align=center]]:text-center [[align=right]]:text-right",
        className
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }) => (
    <td
      className={cn(
        "aui-md-td border-s border-b border-muted-foreground/20 px-2 py-1 text-start last:border-e [[align=center]]:text-center [[align=right]]:text-right",
        className
      )}
      {...props}
    />
  ),
  tr: ({ className, ...props }) => (
    <tr
      className={cn(
        "aui-md-tr m-0 border-b p-0 first:border-t [&:last-child>td:first-child]:rounded-es-lg [&:last-child>td:last-child]:rounded-ee-lg",
        className
      )}
      {...props}
    />
  ),
  li: ({ className, ...props }) => (
    <li className={cn("aui-md-li leading-normal", className)} {...props} />
  ),
  sup: ({ className, ...props }) => (
    <sup
      className={cn("aui-md-sup [&>a]:text-xs [&>a]:no-underline", className)}
      {...props}
    />
  ),
  pre: ({ className, ...props }) => (
    <pre
      className={cn(
        "aui-md-pre overflow-x-auto rounded-t-none rounded-b-lg border border-t-0 border-border/50 bg-muted/30 p-3 text-xs leading-relaxed",
        className
      )}
      {...props}
    />
  ),
  code: function Code({ className, ...props }) {
    const isCodeBlock = useIsMarkdownCodeBlock()
    return (
      <code
        className={cn(
          !isCodeBlock &&
            "aui-md-inline-code rounded-md border border-border/50 bg-muted/50 px-1.5 py-0.5 font-mono text-[0.85em]",
          className
        )}
        {...props}
      />
    )
  },
  CodeHeader,
})
