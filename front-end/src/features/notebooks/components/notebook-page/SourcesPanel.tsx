import * as React from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertCircleIcon,
  DownloadIcon,
  ExternalLinkIcon,
  EyeIcon,
  FileTextIcon,
  Loader2Icon,
  MoreVerticalIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  PlusIcon,
  Search,
  Trash2Icon,
  UploadIcon,
} from "lucide-react"
import { toast } from "sonner"

import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { getPresignedUploadUrl, reportUploadFailed } from "@/features/files/api"
import {
  getNotebookDocumentPreview,
  useNotebookDocumentEvents,
  useDeleteNotebookDocumentMutation,
  useNotebookDocumentsQuery,
} from "@/features/notebooks/api"
import type {
  NotebookDocument,
  NotebookDocumentPreview,
} from "@/features/notebooks/types"
import { cn } from "@/lib/utils"

const MAX_FILE_SIZE = 10 * 1024 * 1024
const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"]
const SAFE_UPLOAD_CONTENT_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
])
const SAFE_INLINE_PREVIEW_CONTENT_TYPES = new Set([
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
])

type UploadState = "idle" | "uploading"

export function SourcesPanel({
  notebookId,
  isCollapsed,
  onToggleCollapse,
}: {
  notebookId: string
  isCollapsed?: boolean
  onToggleCollapse?: () => void
}) {
  const queryClient = useQueryClient()
  const streamHealth = useNotebookDocumentEvents(notebookId)
  const {
    data: documents = [],
    isLoading,
    isError,
  } = useNotebookDocumentsQuery(notebookId, streamHealth)
  const [searchValue, setSearchValue] = React.useState("")
  const [uploadState, setUploadState] = React.useState<UploadState>("idle")
  const [uploadProgress, setUploadProgress] = React.useState(0)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const xhrRef = React.useRef<XMLHttpRequest | null>(null)

  React.useEffect(() => {
    return () => xhrRef.current?.abort()
  }, [])

  const filteredDocuments = React.useMemo(() => {
    const query = searchValue.trim().toLowerCase()
    if (!query) {
      return documents
    }
    return documents.filter((document) =>
      document.filename.toLowerCase().includes(query)
    )
  }, [documents, searchValue])

  const handleFileChange = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file || uploadState === "uploading") {
      return
    }

    if (!isSupportedFile(file)) {
      toast.error("Unsupported source type", {
        description:
          "Upload PDF, DOCX, TXT, or Markdown files for notebook ingestion.",
      })
      return
    }

    if (!isSafeUploadContentType(file)) {
      toast.error("Unsupported source content", {
        description:
          "Only PDF, DOCX, plain text, or Markdown content can be uploaded.",
      })
      return
    }

    if (file.size > MAX_FILE_SIZE) {
      toast.error("File is too large", {
        description: "Maximum file size is 10MB.",
      })
      return
    }

    await uploadNotebookSource(file, notebookId, {
      onStart: () => {
        setUploadState("uploading")
        setUploadProgress(0)
      },
      onProgress: setUploadProgress,
      onXhr: (xhr) => {
        xhrRef.current = xhr
      },
      onSuccess: async () => {
        toast.success("Source uploaded", {
          description: `${file.name} was sent to the ingestion pipeline.`,
        })
        await Promise.all([
          queryClient.invalidateQueries({
            queryKey: ["notebooks", notebookId, "documents"],
          }),
          queryClient.invalidateQueries({ queryKey: ["notebooks"] }),
        ])
      },
      onError: (message) => {
        toast.error("Upload failed", { description: message })
      },
      onSettled: () => {
        xhrRef.current = null
        setUploadState("idle")
        setUploadProgress(0)
      },
    })
  }

  const openFilePicker = () => fileInputRef.current?.click()

  const hasDocuments = filteredDocuments.length > 0
  const isUploading = uploadState === "uploading"

  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col bg-card transition-all duration-300",
        isCollapsed ? "w-14 shrink-0 items-center gap-3 py-2" : ""
      )}
    >
      {isCollapsed ? (
        <>
          <Tooltip>
            <TooltipTrigger
              onClick={onToggleCollapse}
              className="flex size-8 shrink-0 items-center justify-center rounded-2xl text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Expand panel"
            >
              <PanelLeftOpenIcon className="size-4" />
            </TooltipTrigger>
            <TooltipContent side="right">Expand panel</TooltipContent>
          </Tooltip>

          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept={SUPPORTED_EXTENSIONS.join(",")}
            onChange={handleFileChange}
          />

          <Tooltip>
            <TooltipTrigger
              onClick={openFilePicker}
              disabled={isUploading}
              className="my-2 flex size-8 shrink-0 items-center justify-center rounded-2xl border border-dashed text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
              aria-label="Add source"
            >
              {isUploading ? (
                <Loader2Icon className="size-4 animate-spin" />
              ) : (
                <PlusIcon className="size-4" />
              )}
            </TooltipTrigger>
            <TooltipContent side="right">
              {isUploading ? `Uploading ${uploadProgress}%` : "Add source"}
            </TooltipContent>
          </Tooltip>

          {documents.length > 0 && (
            <ScrollArea className="min-h-0 w-full flex-1">
              <div className="flex flex-col items-center gap-2.5 px-2 pb-4">
                {documents.map((document) => (
                  <CollapsedSourceItem key={document.id} document={document} />
                ))}
              </div>
            </ScrollArea>
          )}
        </>
      ) : (
        <>
          <div className="flex w-full flex-col gap-2 border-b px-3 py-3">
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept={SUPPORTED_EXTENSIONS.join(",")}
              onChange={handleFileChange}
            />
            <Button
              type="button"
              variant="outline"
              disabled={isUploading}
              onClick={openFilePicker}
              className="my-2 w-full justify-start border-dashed"
            >
              {isUploading ? (
                <Loader2Icon
                  data-icon="inline-start"
                  className="animate-spin"
                />
              ) : (
                <PlusIcon data-icon="inline-start" />
              )}
              {isUploading ? `Uploading ${uploadProgress}%` : "Add source"}
            </Button>
            {isUploading ? <Progress value={uploadProgress} /> : null}

            {onToggleCollapse ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onToggleCollapse}
                className="justify-start text-muted-foreground"
              >
                <PanelLeftCloseIcon data-icon="inline-start" />
                Collapse panel
              </Button>
            ) : null}
          </div>

          <ScrollArea className="min-h-0 w-full flex-1">
            <div className="px-3 pt-3">
              <InputGroup className="w-full bg-muted/40">
                <InputGroupAddon>
                  <Search className="size-4" />
                </InputGroupAddon>
                <InputGroupInput
                  placeholder="Search uploaded sources"
                  className="text-xs"
                  value={searchValue}
                  onChange={(e) => setSearchValue(e.target.value)}
                />
                <InputGroupAddon
                  align="inline-end"
                  className="text-[10px] text-muted-foreground select-none"
                >
                  {filteredDocuments.length}{" "}
                  {filteredDocuments.length === 1 ? "result" : "results"}
                </InputGroupAddon>
              </InputGroup>
            </div>
            {isLoading ? (
              <SourcesPlaceholder label="Loading sources..." />
            ) : isError ? (
              <SourcesPlaceholder
                icon={<AlertCircleIcon className="size-5" />}
                label="Sources could not be loaded"
                description="Refresh the page or try again after the API is available."
              />
            ) : hasDocuments ? (
              <div className="mt-3 flex flex-col items-start gap-2 px-3 pb-3">
                {filteredDocuments.map((document) => (
                  <SourceItem key={document.id} document={document} />
                ))}
              </div>
            ) : (
              <Empty className="border-0 px-6 py-12">
                <EmptyHeader>
                  <EmptyTitle className="text-sm">
                    {documents.length > 0
                      ? "No matching sources"
                      : "Saved sources will appear here"}
                  </EmptyTitle>
                  <EmptyDescription className="text-xs">
                    {documents.length > 0
                      ? "Try a different filename search."
                      : "Click Add source above to upload PDF, DOCX, TXT, or Markdown files."}
                  </EmptyDescription>
                </EmptyHeader>
                {documents.length === 0 && (
                  <EmptyContent>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isUploading}
                      onClick={openFilePicker}
                    >
                      <UploadIcon data-icon="inline-start" />
                      Import file
                    </Button>
                  </EmptyContent>
                )}
              </Empty>
            )}
          </ScrollArea>
        </>
      )}
    </div>
  )
}

function SourceItem({ document }: { document: NotebookDocument }) {
  const status = getDocumentStatus(document.status)
  const [isPreviewOpen, setIsPreviewOpen] = React.useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = React.useState(false)
  const deleteDocumentMutation = useDeleteNotebookDocumentMutation()

  const handleDeleteSource = async () => {
    try {
      await deleteDocumentMutation.mutateAsync({
        notebookId: document.notebookId,
        documentId: document.id,
      })
      toast.success("Source deleted", {
        description: `${document.filename} was removed from this notebook.`,
      })
      setIsDeleteDialogOpen(false)
    } catch (error) {
      toast.error("Delete failed", {
        description:
          error instanceof Error
            ? error.message
            : "The source could not be deleted.",
      })
    }
  }

  return (
    <>
      <AlertDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
      >
        <Card size="sm" className="h-auto w-full self-start py-0">
          <CardContent className="px-2 py-1.5">
            <div className="flex items-center gap-2.5">
              <button
                type="button"
                className="min-w-0 flex-1 rounded-xl px-1 py-1 text-left transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none"
                onClick={() => setIsPreviewOpen(true)}
              >
                <span
                  className="block truncate text-xs font-medium text-foreground"
                  title={document.filename}
                >
                  {document.filename}
                </span>
                <span className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                  <span>{formatBytes(document.size)}</span>
                  <span aria-hidden="true">/</span>
                  <Badge variant={status.variant}>{status.label}</Badge>
                </span>
                {document.status === "failed" && document.errorMessage ? (
                  <span className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-destructive">
                    {document.errorMessage}
                  </span>
                ) : null}
              </button>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="self-center text-muted-foreground"
                      aria-label={`Open actions for ${document.filename}`}
                    />
                  }
                >
                  <MoreVerticalIcon />
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-36" align="end">
                  <DropdownMenuGroup>
                    <DropdownMenuItem onClick={() => setIsPreviewOpen(true)}>
                      <EyeIcon data-icon="inline-start" />
                      <span>Preview</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      onClick={() => setIsDeleteDialogOpen(true)}
                      disabled={deleteDocumentMutation.isPending}
                    >
                      <Trash2Icon data-icon="inline-start" />
                      <span>Delete</span>
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </CardContent>
        </Card>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete source?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes "{document.filename}" from the notebook context. This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteDocumentMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteDocumentMutation.isPending}
              onClick={handleDeleteSource}
            >
              {deleteDocumentMutation.isPending ? (
                <Loader2Icon data-icon="inline-start" className="animate-spin" />
              ) : (
                <Trash2Icon data-icon="inline-start" />
              )}
              Delete source
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <SourcePreviewDialog
        document={document}
        open={isPreviewOpen}
        onOpenChange={setIsPreviewOpen}
      />
    </>
  )
}

function CollapsedSourceItem({ document }: { document: NotebookDocument }) {
  const status = getDocumentStatus(document.status)
  const [isPreviewOpen, setIsPreviewOpen] = React.useState(false)

  return (
    <>
      <Tooltip>
        <TooltipTrigger
          onClick={() => setIsPreviewOpen(true)}
          className="flex size-8 shrink-0 items-center justify-center rounded-2xl border bg-muted text-muted-foreground transition-all duration-200 hover:scale-105 hover:text-foreground"
          aria-label={`Preview ${document.filename}`}
        >
          <FileTextIcon className="size-4" />
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-xs break-all">
          <div className="space-y-0.5">
            <p className="text-xs leading-tight font-medium">
              {document.filename}
            </p>
            <p className="text-[10px] leading-normal text-muted-foreground">
              {formatBytes(document.size)} / {status.label}
            </p>
          </div>
        </TooltipContent>
      </Tooltip>
      <SourcePreviewDialog
        document={document}
        open={isPreviewOpen}
        onOpenChange={setIsPreviewOpen}
      />
    </>
  )
}

function SourcePreviewDialog({
  document,
  open,
  onOpenChange,
}: {
  document: NotebookDocument
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const {
    data: preview = null,
    error,
    isLoading,
  } = useQuery({
    queryKey: [
      "notebooks",
      document.notebookId,
      "documents",
      document.id,
      "preview",
    ],
    queryFn: () => getNotebookDocumentPreview(document.notebookId, document.id),
    enabled: open,
    staleTime: 55 * 60 * 1000,
  })

  const canRenderInline = preview ? canRenderPreviewInline(preview) : false
  const sourceUrl = preview?.url ?? null
  const errorMessage =
    error instanceof Error ? error.message : "The document could not be opened."

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92dvh] gap-4 overflow-hidden sm:max-w-5xl">
        <DialogHeader className="pr-10">
          <DialogTitle className="truncate" title={document.filename}>
            {document.filename}
          </DialogTitle>
          <DialogDescription>
            {formatBytes(document.size)} / {getDocumentStatus(document.status).label}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-[55dvh] overflow-hidden rounded-2xl border bg-muted/30">
          {isLoading ? (
            <div className="flex h-[55dvh] items-center justify-center text-sm text-muted-foreground">
              <Loader2Icon className="mr-2 size-4 animate-spin" />
              Loading preview
            </div>
          ) : error ? (
            <div className="flex h-[55dvh] flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground">
              <AlertCircleIcon className="size-5 text-destructive" />
              <p>{errorMessage}</p>
            </div>
          ) : preview?.previewType === "text" ? (
            <ScrollArea className="h-[55dvh]">
              <pre className="whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-foreground">
                {preview.content}
              </pre>
            </ScrollArea>
          ) : sourceUrl && canRenderInline ? (
            <iframe
              title={preview.filename}
              src={sourceUrl}
              sandbox=""
              className="h-[55dvh] w-full bg-background"
            />
          ) : (
            <div className="flex h-[55dvh] flex-col items-center justify-center gap-3 px-6 text-center text-sm text-muted-foreground">
              <FileTextIcon className="size-8" />
              <p>Preview is available as a separate document view.</p>
            </div>
          )}
        </div>

        <DialogFooter>
          {sourceUrl ? (
            <>
              <Button
                variant="outline"
                render={
                  <a href={sourceUrl} target="_blank" rel="noreferrer" />
                }
              >
                <ExternalLinkIcon data-icon="inline-start" />
                Open
              </Button>
              <Button
                variant="outline"
                render={<a href={sourceUrl} download={preview?.filename} />}
              >
                <DownloadIcon data-icon="inline-start" />
                Download
              </Button>
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SourcesPlaceholder({
  icon,
  label,
  description,
}: {
  icon?: React.ReactNode
  label: string
  description?: string
}) {
  return (
    <Empty className="border-0 px-6 py-12">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          {icon ?? <Loader2Icon className="size-5 animate-spin" />}
        </EmptyMedia>
        <EmptyTitle className="text-sm">{label}</EmptyTitle>
        {description ? (
          <EmptyDescription className="text-xs">{description}</EmptyDescription>
        ) : null}
      </EmptyHeader>
    </Empty>
  )
}

function isSupportedFile(file: File) {
  const filename = file.name.toLowerCase()
  return SUPPORTED_EXTENSIONS.some((extension) => filename.endsWith(extension))
}

function isSafeUploadContentType(file: File) {
  const contentType = normalizeContentType(file.type)
  if (!contentType) {
    return true
  }
  return SAFE_UPLOAD_CONTENT_TYPES.has(contentType)
}

function formatBytes(bytes: number | null) {
  if (!bytes) {
    return "Size pending"
  }

  const units = ["B", "KB", "MB", "GB"]
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  )
  return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function getDocumentStatus(status: string) {
  switch (status) {
    case "indexed":
      return {
        label: "Indexed",
        variant: "secondary" as const,
      }
    case "indexing":
      return {
        label: "Indexing",
        variant: "outline" as const,
      }
    case "failed":
      return {
        label: "Failed",
        variant: "destructive" as const,
      }
    case "processing":
      return {
        label: "Processing",
        variant: "outline" as const,
      }
    case "uploaded":
      return {
        label: "Queued",
        variant: "outline" as const,
      }
    default:
      return {
        label: "Waiting for upload",
        variant: "outline" as const,
      }
  }
}

function canRenderPreviewInline(preview: NotebookDocumentPreview) {
  const contentType = normalizeContentType(preview.contentType)
  const filename = preview.filename.toLowerCase()
  if (contentType) {
    return SAFE_INLINE_PREVIEW_CONTENT_TYPES.has(contentType)
  }

  return (
    filename.endsWith(".pdf") ||
    filename.endsWith(".txt") ||
    filename.endsWith(".md")
  )
}

function normalizeContentType(contentType: string | null | undefined) {
  return contentType?.split(";")[0]?.trim().toLowerCase() ?? ""
}

async function uploadNotebookSource(
  file: File,
  notebookId: string,
  callbacks: {
    onStart: () => void
    onProgress: (progress: number) => void
    onXhr: (xhr: XMLHttpRequest) => void
    onSuccess: () => Promise<void>
    onError: (message: string) => void
    onSettled: () => void
  }
) {
  callbacks.onStart()
  let key: string | undefined

  try {
    const contentType = file.type || "application/octet-stream"
    const presigned = await getPresignedUploadUrl(
      file.name,
      contentType,
      notebookId
    )
    const { url } = presigned
    key = presigned.key

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      callbacks.onXhr(xhr)
      xhr.open("PUT", url, true)
      xhr.setRequestHeader("Content-Type", contentType)

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          callbacks.onProgress(Math.round((event.loaded / event.total) * 100))
        }
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          callbacks.onProgress(100)
          resolve()
          return
        }
        reject(
          new Error(
            `Storage upload failed: HTTP ${xhr.status} ${xhr.statusText}`
          )
        )
      }

      xhr.onerror = () =>
        reject(new Error("Network error while uploading to storage."))
      xhr.onabort = () => reject(new Error("Upload was cancelled."))
      xhr.send(file)
    })

    await callbacks.onSuccess()
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "The source could not be uploaded."
    try {
      if (typeof key === "string" && key.length > 0) {
        await reportUploadFailed(key, notebookId, message)
      }
    } catch {
      // Best-effort failure reporting; keep original error surfaced to user.
    }
    callbacks.onError(message)
  } finally {
    callbacks.onSettled()
  }
}
