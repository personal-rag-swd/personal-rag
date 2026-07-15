import { ExternalLink } from "lucide-react"

import { ReactDocViewer } from "@/components/document-preview/react-doc-viewer"
import { buttonVariants } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { useAdminDocumentPreviewQuery } from "../api"
import type { AdminDocument } from "../types"

export function DocumentPreviewDialog({
  document,
  onClose,
}: {
  document: AdminDocument
  onClose: () => void
}) {
  const { data: preview, isLoading, isError } = useAdminDocumentPreviewQuery(
    document.id
  )

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex h-[90vh] max-w-[90vw] flex-col gap-4 sm:max-w-6xl">
        <DialogHeader className="pr-10">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 space-y-1">
              <DialogTitle className="truncate">
                {document.filename}
              </DialogTitle>
              <DialogDescription>
                {document.contentType ?? "Unknown type"}
                {document.size !== null
                  ? ` · ${(document.size / 1024).toFixed(1)} KB`
                  : ""}
              </DialogDescription>
            </div>
            {preview?.url ? (
              <a
                href={preview.url}
                target="_blank"
                rel="noreferrer"
                className={cn(
                  buttonVariants({ variant: "outline", size: "sm" }),
                  "shrink-0"
                )}
              >
                <ExternalLink className="size-4" />
                Open in new tab
              </a>
            ) : null}
          </div>
        </DialogHeader>
        <div className="min-h-0 flex-1">
          {isLoading || !preview ? (
            <Skeleton className="h-full w-full" />
          ) : isError ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Failed to load document preview.
            </div>
          ) : preview.previewType === "text" ? (
            <pre className="h-full overflow-auto rounded-md border bg-muted/30 p-4 text-sm whitespace-pre-wrap">
              {preview.content}
            </pre>
          ) : preview.url ? (
            <ReactDocViewer
              src={preview.url}
              filename={preview.filename}
              contentType={preview.contentType}
              fallback={
                <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
                  <p>Unable to render this document in the viewer.</p>
                  <a
                    href={preview.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary underline"
                  >
                    Open in a new tab
                  </a>
                </div>
              }
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No preview available.
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
