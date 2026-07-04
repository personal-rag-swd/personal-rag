import * as React from "react"
import { UDocClient } from "@docmentis/udoc-viewer"
import { ExternalLink } from "lucide-react"

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

type UDocClientInstance = Awaited<ReturnType<typeof UDocClient.create>>
type UDocViewerInstance = Awaited<
  ReturnType<UDocClientInstance["createViewer"]>
>

function UDocViewer({ src }: { src: string }) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let disposed = false
    let client: UDocClientInstance | undefined
    let viewer: UDocViewerInstance | undefined
    const container = containerRef.current

    void (async () => {
      try {
        client = await UDocClient.create()
        if (disposed || !container) return
        viewer = await client.createViewer({ container })
        if (disposed) return
        await viewer.load(src)
      } catch {
        if (!disposed) setError("Unable to render this document in the viewer.")
      }
    })()

    return () => {
      disposed = true
      viewer?.destroy()
      client?.destroy()
    }
  }, [src])

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
        <p>{error}</p>
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          className="text-primary underline"
        >
          Open in a new tab
        </a>
      </div>
    )
  }

  return <div ref={containerRef} className="h-full w-full" />
}

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
            <UDocViewer src={preview.url} />
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
