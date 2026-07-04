import * as React from "react"
import { UDocClient } from "@docmentis/udoc-viewer"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
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
      <div className="flex h-[70vh] flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
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

  return <div ref={containerRef} className="h-[70vh] w-full" />
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
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="truncate">{document.filename}</DialogTitle>
          <DialogDescription>
            {document.contentType ?? "Unknown type"}
            {document.size !== null
              ? ` · ${(document.size / 1024).toFixed(1)} KB`
              : ""}
          </DialogDescription>
        </DialogHeader>
        {isLoading || !preview ? (
          <Skeleton className="h-[70vh] w-full" />
        ) : isError ? (
          <div className="flex h-[70vh] items-center justify-center text-sm text-muted-foreground">
            Failed to load document preview.
          </div>
        ) : preview.previewType === "text" ? (
          <pre className="max-h-[70vh] overflow-auto rounded-md border bg-muted/30 p-4 text-sm whitespace-pre-wrap">
            {preview.content}
          </pre>
        ) : preview.url ? (
          <UDocViewer src={preview.url} />
        ) : (
          <div className="flex h-[70vh] items-center justify-center text-sm text-muted-foreground">
            No preview available.
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
