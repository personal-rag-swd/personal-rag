import DocViewer, { DocViewerRenderers, type IDocument } from "@iamjariwala/react-doc-viewer"
import "@iamjariwala/react-doc-viewer/dist/index.css"

export function ReactDocViewerRuntime({ document }: { document: IDocument }) {
  return (
    <DocViewer
      className="h-full w-full"
      documents={[document]}
      pluginRenderers={DocViewerRenderers}
      prefetchMethod="GET"
      config={{
        header: { disableFileName: true },
        dragDrop: { enableDragDrop: false },
        themeMode: "auto",
      }}
    />
  )
}
