import * as React from "react"
import { UDocClient } from "@docmentis/udoc-viewer"

type UDocClientInstance = Awaited<ReturnType<typeof UDocClient.create>>
type UDocViewerInstance = Awaited<
  ReturnType<UDocClientInstance["createViewer"]>
>

export function UDocViewer({
  src,
  fallback,
}: {
  src: string
  fallback?: React.ReactNode
}) {
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
    return fallback ?? null
  }

  return <div ref={containerRef} className="h-full w-full" />
}
