import * as React from "react"
import type { IDocument } from "@iamjariwala/react-doc-viewer"

const ReactDocViewerRuntime = React.lazy(async () => {
  const module = await import("./react-doc-viewer-runtime")
  return { default: module.ReactDocViewerRuntime }
})

export function ReactDocViewer({
  src,
  filename,
  contentType,
  fallback,
}: {
  src: string
  filename: string
  contentType?: string | null
  fallback?: React.ReactNode
}) {
  const document = React.useMemo<IDocument>(
    () => ({ uri: src, fileName: filename, fileType: contentType ?? undefined }),
    [contentType, filename, src]
  )

  return (
    <React.Suspense
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading document viewer
        </div>
      }
    >
      <ViewerErrorBoundary key={src} fallback={fallback}>
        <ReactDocViewerRuntime document={document} />
      </ViewerErrorBoundary>
    </React.Suspense>
  )
}

class ViewerErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    return this.state.hasError ? (this.props.fallback ?? null) : this.props.children
  }
}
