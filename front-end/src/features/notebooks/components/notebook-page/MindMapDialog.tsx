import * as React from "react"
import {
  useState,
  useRef,
  useEffect,
  useMemo,
  useCallback,
  useContext,
  createContext,
} from "react"
import {
  Background,
  BackgroundVariant,
  type Edge,
  Handle,
  MarkerType,
  type Node,
  type NodeChange,
  type NodeProps,
  Position as FlowPosition,
  ReactFlow,
  type ReactFlowInstance,
  useNodesState,
} from "@xyflow/react"
import "@xyflow/react/dist/base.css"
import { toPng } from "html-to-image"
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FileJsonIcon,
  ImageIcon,
  Maximize2Icon,
  Minimize2Icon,
  SearchIcon,
  XIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react"
import { toast } from "sonner"
import { formatDistanceToNow } from "date-fns"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Field,
  FieldContent,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

import { useNotebookReportsQuery } from "@/features/notebooks/api"
import type {
  MindMapContent,
  MindMapNode,
  NotebookReport,
} from "@/features/notebooks/types"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LayoutPosition = { x: number; y: number; width: number; height: number }

type MindMapNodeVariant = "root" | "main" | "sub"
type HighlightState = "normal" | "highlighted" | "dimmed"

type MindMapFlowNodeData = {
  label: string
  description?: string | null
  variant: MindMapNodeVariant
  highlightState: HighlightState
  isExpanded: boolean
  canToggle: boolean
}

type MindMapFlowNode = Node<MindMapFlowNodeData>
type MindMapFlowEdge = Edge

type LayoutResult = {
  positions: Record<string, LayoutPosition>
  rootNode: MindMapNode
  mainNodes: MindMapNode[]
  subNodes: MindMapNode[]
}

// ---------------------------------------------------------------------------
// Context – provides stable action callbacks to custom node components.
// Using a context (instead of callbacks in `data`) means custom nodes never
// capture stale closures and React Flow never sees data changes that would
// trigger unmount/remount of nodes mid-interaction.
// ---------------------------------------------------------------------------

type MindMapActions = {
  toggle: (nodeId: string) => void
}

const MindMapActionsCtx = createContext<MindMapActions | null>(null)

function useMindMapActions(): MindMapActions {
  const ctx = useContext(MindMapActionsCtx)
  if (!ctx) throw new Error("useMindMapActions must be used inside MindMapActionsCtx.Provider")
  return ctx
}

// ---------------------------------------------------------------------------
// NODE_TYPES must be defined outside any component so React Flow doesn't
// recreate the map on every render (which would remount all custom nodes).
// ---------------------------------------------------------------------------

const HIDDEN_HANDLE_CLASS =
  "!size-0 !border-0 !bg-transparent !opacity-0 pointer-events-none"

const NODE_TYPES = {
  root: MindMapCanvasNode,
  main: MindMapCanvasNode,
  sub: MindMapCanvasNode,
} as const

// ---------------------------------------------------------------------------
// MindMapDialog – the public component
// ---------------------------------------------------------------------------

export function MindMapDialog({
  notebookId,
  notebookName,
  open,
  onOpenChange,
  initialMap,
  onRequestGenerateNew,
}: {
  notebookId: string
  notebookName: string
  open: boolean
  onOpenChange: (open: boolean) => void
  initialMap?: NotebookReport | null
  onRequestGenerateNew?: () => void
}) {
  const [selectedMap, setSelectedMap] = useState<NotebookReport | null>(() =>
    initialMap?.reportType === "mindmap" ? initialMap : null
  )

  const [isRootExpanded, setIsRootExpanded] = useState(false)
  const [expandedMainNodeIds, setExpandedMainNodeIds] = useState<Set<string>>(
    new Set()
  )
  const [pendingFocusNodeIds, setPendingFocusNodeIds] = useState<
    string[] | null
  >(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const { data: reports } = useNotebookReportsQuery(notebookId)

  const mindMaps = useMemo(() => {
    if (!reports) return []
    return reports.filter(
      (report): report is NotebookReport & { reportType: "mindmap" } =>
        report.reportType === "mindmap"
    )
  }, [reports])

  const activeMap = useMemo(() => {
    if (selectedMap && selectedMap.reportType === "mindmap") return selectedMap
    if (mindMaps.length > 0) return mindMaps[0]
    return null
  }, [selectedMap, mindMaps])

  const activeMapId = activeMap?.id ?? null
  const prevActiveMapIdRef = useRef<string | null>(activeMapId)

  useEffect(() => {
    if (activeMapId === prevActiveMapIdRef.current) return
    prevActiveMapIdRef.current = activeMapId
    setIsRootExpanded(false)
    setExpandedMainNodeIds(new Set())
    setPendingFocusNodeIds(null)
    setSelectedNodeId(null)
    setSearchQuery("")
  }, [activeMapId])

  const graphData = useMemo(
    () => (activeMap ? activeMap.content : null),
    [activeMap]
  )

  // -------------------------------------------------------------------------
  // Layout computation
  // -------------------------------------------------------------------------

  const layout = useMemo<LayoutResult | null>(() => {
    if (!graphData?.nodes?.length) return null

    const nodes = graphData.nodes
    const rootNode = nodes.find((n) => n.type === "root") ?? nodes[0]
    if (!rootNode) return null

    const mainNodes = isRootExpanded
      ? nodes.filter((n) => n.type === "main" && n.id !== rootNode.id)
      : []
    const subNodes = isRootExpanded
      ? nodes.filter(
          (n) => n.type === "sub" && expandedMainNodeIds.has(n.parentId ?? "")
        )
      : []

    const positions: Record<string, LayoutPosition> = {}
    const nodeWidths = { root: 280, main: 248, sub: 220 }
    const nodeHeights = { root: 104, main: 92, sub: 74 }
    const xSpacing = 360
    const subYSpacing = 92
    const mainGap = 70

    const getSubtreeHeight = (children: MindMapNode[]) =>
      Math.max(1, children.length) * subYSpacing

    const positionSide = (branchNodes: MindMapNode[], isRight: boolean) => {
      const xDir = isRight ? 1 : -1
      const branchHeights: Record<string, number> = {}
      let totalHeight = 0

      branchNodes.forEach((bn) => {
        const children = subNodes.filter((c) => c.parentId === bn.id)
        const h = getSubtreeHeight(children)
        branchHeights[bn.id] = h
        totalHeight += h
      })

      if (branchNodes.length > 1) totalHeight += (branchNodes.length - 1) * mainGap

      let currentY = -totalHeight / 2

      branchNodes.forEach((bn) => {
        const children = subNodes.filter((c) => c.parentId === bn.id)
        const subtreeH = branchHeights[bn.id]
        const centerY = currentY + subtreeH / 2
        const centerX = xDir * xSpacing

        positions[bn.id] = {
          x: centerX - nodeWidths.main / 2,
          y: centerY - nodeHeights.main / 2,
          width: nodeWidths.main,
          height: nodeHeights.main,
        }

        children.forEach((child, i) => {
          const childX = xDir * 2 * xSpacing
          const childY = centerY + (i - (children.length - 1) / 2) * subYSpacing
          positions[child.id] = {
            x: childX - nodeWidths.sub / 2,
            y: childY - nodeHeights.sub / 2,
            width: nodeWidths.sub,
            height: nodeHeights.sub,
          }
        })

        currentY += subtreeH + mainGap
      })
    }

    positions[rootNode.id] = {
      x: -nodeWidths.root / 2,
      y: -nodeHeights.root / 2,
      width: nodeWidths.root,
      height: nodeHeights.root,
    }

    positionSide(mainNodes, true)

    return { positions, rootNode, mainNodes, subNodes }
  }, [graphData, isRootExpanded, expandedMainNodeIds])

  // -------------------------------------------------------------------------
  // Derived display state
  // -------------------------------------------------------------------------

  const selectedNode = useMemo(
    () =>
      graphData && selectedNodeId
        ? (graphData.nodes.find((n) => n.id === selectedNodeId) ?? null)
        : null,
    [graphData, selectedNodeId]
  )

  const selectedNodeRelationships = useMemo(
    () =>
      graphData && selectedNodeId
        ? (graphData.relationships ?? []).filter(
            (r) => r.source === selectedNodeId || r.target === selectedNodeId
          )
        : [],
    [graphData, selectedNodeId]
  )

  // -------------------------------------------------------------------------
  // Expand / collapse helpers
  // -------------------------------------------------------------------------

  const expandRoot = useCallback(() => {
    setIsRootExpanded(true)
    if (!graphData?.nodes?.length) return
    const root = graphData.nodes.find((n) => n.type === "root") ?? graphData.nodes[0]
    const mains = graphData.nodes.filter((n) => n.type === "main" && n.id !== root.id)
    setPendingFocusNodeIds([root.id, ...mains.map((n) => n.id)])
  }, [graphData])

  const collapseRoot = useCallback(() => {
    if (!graphData?.nodes?.length) return
    const root = graphData.nodes.find((n) => n.type === "root") ?? graphData.nodes[0]
    setIsRootExpanded(false)
    setExpandedMainNodeIds(new Set())
    setPendingFocusNodeIds([root.id])
  }, [graphData])

  const expandMainNode = useCallback(
    (nodeId: string) => {
      setExpandedMainNodeIds((prev) => {
        const next = new Set(prev)
        next.add(nodeId)
        return next
      })
      if (!graphData?.nodes?.length) return
      const childIds = graphData.nodes
        .filter((n) => n.parentId === nodeId)
        .map((n) => n.id)
      setPendingFocusNodeIds([nodeId, ...childIds])
    },
    [graphData]
  )

  const collapseMainNode = useCallback(
    (nodeId: string) => {
      setExpandedMainNodeIds((prev) => {
        const next = new Set(prev)
        next.delete(nodeId)
        return next
      })
      if (!graphData?.nodes?.length) return
      const root = graphData.nodes.find((n) => n.type === "root") ?? graphData.nodes[0]
      const isMobile = window.innerWidth < 640
      setPendingFocusNodeIds(isMobile ? [nodeId] : [nodeId, root.id])
    },
    [graphData]
  )

  const toggleNode = useCallback(
    (nodeId: string) => {
      if (!graphData?.nodes?.length) return
      const node = graphData.nodes.find((n) => n.id === nodeId)
      if (!node) return

      if (node.type === "root") {
        if (isRootExpanded) {
          collapseRoot()
        } else {
          expandRoot()
        }
        return
      }
      if (node.type === "main") {
        if (expandedMainNodeIds.has(nodeId)) {
          collapseMainNode(nodeId)
        } else {
          expandMainNode(nodeId)
        }
      }
    },
    [
      collapseMainNode,
      collapseRoot,
      expandMainNode,
      expandRoot,
      expandedMainNodeIds,
      graphData,
      isRootExpanded,
    ]
  )

  const handleSelectNode = useCallback(
    (nodeId: string) => {
      if (!graphData?.nodes?.length) return
      const node = graphData.nodes.find((n) => n.id === nodeId)
      if (!node) return

      setSelectedNodeId(nodeId)
      if (node.type === "root" && !isRootExpanded) {
        expandRoot()
        return
      }
      if (node.type === "main" && !expandedMainNodeIds.has(nodeId)) {
        expandMainNode(nodeId)
      }
    },
    [expandMainNode, expandRoot, expandedMainNodeIds, graphData, isRootExpanded]
  )

  // -------------------------------------------------------------------------
  // Search highlight
  // -------------------------------------------------------------------------

  const getHighlightState = useCallback(
    (label: string, description?: string | null): HighlightState => {
      if (!searchQuery.trim()) return "normal"
      const haystack = `${label} ${description ?? ""}`.toLowerCase()
      return haystack.includes(searchQuery.toLowerCase()) ? "highlighted" : "dimmed"
    },
    [searchQuery]
  )

  // -------------------------------------------------------------------------
  // Flow nodes & edges
  // -------------------------------------------------------------------------

  const flowNodes = useMemo<MindMapFlowNode[]>(() => {
    if (!graphData?.nodes?.length || !layout) return []

    return Object.entries(layout.positions).flatMap(([nodeId, position]) => {
      const node = graphData.nodes.find((n) => n.id === nodeId)
      if (!node) return []

      const isExpanded =
        node.type === "root" ? isRootExpanded : expandedMainNodeIds.has(node.id)

      return [
        {
          id: node.id,
          type: node.type,
          position: { x: position.x, y: position.y },
          sourcePosition: FlowPosition.Right,
          targetPosition: FlowPosition.Left,
          data: {
            label: node.label,
            description: node.description,
            variant: node.type,
            highlightState: getHighlightState(node.label, node.description),
            isExpanded,
            canToggle: node.type !== "sub",
          },
          style: { width: position.width, height: position.height },
        },
      ]
    })
  }, [expandedMainNodeIds, getHighlightState, graphData, isRootExpanded, layout])

  const flowEdges = useMemo<MindMapFlowEdge[]>(() => {
    if (!graphData?.nodes?.length || !layout) return []

    const visibleIds = new Set(flowNodes.map((n) => n.id))

    const hierarchyEdges = flowNodes
      .filter((n) => {
        const src = graphData.nodes.find((item) => item.id === n.id)
        return src?.parentId && visibleIds.has(src.parentId)
      })
      .map((n) => {
        const src = graphData.nodes.find((item) => item.id === n.id)
        const isSub = src?.type === "sub"
        return {
          id: `hierarchy-${n.id}`,
          source: src?.parentId ?? "",
          target: n.id,
          type: "smoothstep",
          animated: false,
          selectable: false,
          style: {
            stroke: isSub ? "rgba(16, 185, 129, 0.32)" : "rgba(59, 130, 246, 0.35)",
            strokeWidth: isSub ? 1.8 : 2.1,
          },
        } satisfies MindMapFlowEdge
      })

    const relationshipEdges = (graphData.relationships ?? [])
      .filter((r) => visibleIds.has(r.source) && visibleIds.has(r.target))
      .map((r, i) => ({
        id: `relationship-${i}`,
        source: r.source,
        target: r.target,
        type: "smoothstep",
        selectable: false,
        label: r.label,
        style: {
          stroke: "rgba(249, 115, 22, 0.75)",
          strokeWidth: 2,
          strokeDasharray: "6 5",
        },
        labelStyle: { fill: "rgb(194, 65, 12)", fontSize: 10, fontWeight: 700 },
        labelBgStyle: {
          fill: "rgba(255, 247, 237, 0.96)",
          fillOpacity: 1,
          stroke: "rgba(249, 115, 22, 0.28)",
          strokeWidth: 1,
        },
        labelBgPadding: [6, 4] as [number, number],
        labelBgBorderRadius: 6,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "rgba(249, 115, 22, 0.75)",
        },
      }))

    return [...hierarchyEdges, ...relationshipEdges]
  }, [flowNodes, graphData, layout])

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[90vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-6xl">
        <DialogHeader className="flex-row items-center justify-between gap-3 border-b px-5 py-3.5 pr-12">
          <div className="min-w-0 flex-1">
            <DialogTitle className="flex min-w-0 items-center gap-2">
              <span className="truncate text-sm">{notebookName}</span>
            </DialogTitle>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {mindMaps.length > 0 ? (
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 gap-1 px-2.5 text-xs font-medium"
                    />
                  }
                >
                  <span className="truncate">
                    V{mindMaps.length - (activeMap ? mindMaps.findIndex(m => m.id === activeMap.id) : 0)}
                  </span>
                  <ChevronDownIcon className="size-3.5 opacity-50" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  {mindMaps.map((map, i) => (
                    <DropdownMenuItem
                      key={map.id}
                      onClick={() => setSelectedMap(map)}
                      className="flex flex-col items-start gap-0.5 py-2"
                    >
                      <span className="font-semibold">V{mindMaps.length - i}</span>
                      <span className="text-[10px] text-muted-foreground">
                        {formatDistanceToNow(new Date(map.createdAt), {
                          addSuffix: true,
                        })}
                      </span>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            ) : null}

            {onRequestGenerateNew ? (
              <Button
                variant="outline"
                size="sm"
                onClick={onRequestGenerateNew}
                className="h-8 gap-1 px-3 text-xs"
              >
                Generate New
              </Button>
            ) : null}
          </div>
        </DialogHeader>

        <div className="relative flex min-h-0 flex-1 overflow-hidden bg-background">
          <MindMapFlowCanvas
            open={open}
            notebookName={notebookName}
            layout={layout}
            flowNodes={flowNodes}
            flowEdges={flowEdges}
            activeMapId={activeMap?.id ?? null}
            selectedNodeId={selectedNodeId}
            setSelectedNodeId={setSelectedNodeId}
            pendingFocusNodeIds={pendingFocusNodeIds}
            setPendingFocusNodeIds={setPendingFocusNodeIds}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            graphData={graphData}
            onGenerateNew={onRequestGenerateNew}
            onToggleNode={toggleNode}
            onSelectNode={handleSelectNode}
          />

          {selectedNode ? (
            <div
              className="absolute inset-0 z-10 cursor-pointer bg-background/50 backdrop-blur-xs sm:hidden"
              onClick={() => setSelectedNodeId(null)}
            />
          ) : null}

          {selectedNode ? (
            <Sheet open={true}>
              <div className="absolute top-0 right-0 bottom-0 z-20 flex w-[85vw] max-w-sm shrink-0 animate-in flex-col overflow-hidden bg-card shadow-2xl duration-250 slide-in-from-right sm:relative sm:w-80 sm:border-l sm:shadow-none">
                <SheetHeader className="flex-row items-center justify-between border-b bg-muted/40 px-4 py-3.5 space-y-0">
                  <SheetTitle className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                    Concept Details
                  </SheetTitle>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setSelectedNodeId(null)}
                    className="size-6 text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <XIcon className="size-3.5" />
                    <span className="sr-only">Close</span>
                  </Button>
                </SheetHeader>

                <ScrollArea className="min-h-0 flex-1">
                  <FieldGroup className="p-4 gap-6">
                    <Field>
                      <div className="flex flex-col gap-3">
                        <Badge
                          variant="outline"
                          className={cn(
                            "w-fit border-none px-2 uppercase text-[10px] font-semibold",
                            selectedNode.type === "root" && "bg-slate-900 text-slate-200",
                            selectedNode.type === "main" && "bg-blue-950 text-blue-400",
                            selectedNode.type === "sub" && "bg-emerald-950 text-emerald-400"
                          )}
                        >
                          {selectedNode.type === "root" && "Central Topic"}
                          {selectedNode.type === "main" && "Core Concept"}
                          {selectedNode.type === "sub" && "Concept Detail"}
                        </Badge>
                        <h3 className="text-base font-bold text-foreground leading-snug">
                          {selectedNode.label}
                        </h3>
                      </div>
                    </Field>

                    <Field>
                      <FieldLabel className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                        Summary & Definition
                      </FieldLabel>
                      <FieldContent>
                        <p className="rounded-lg border border-border bg-muted/40 p-3 text-xs leading-relaxed whitespace-pre-wrap text-foreground select-text">
                          {selectedNode.description ||
                            "No description provided for this concept."}
                        </p>
                      </FieldContent>
                    </Field>

                    {selectedNodeRelationships.length > 0 ? (
                      <Field>
                        <FieldLabel className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                          Concept Relationships
                        </FieldLabel>
                        <FieldContent className="gap-1.5">
                          {selectedNodeRelationships.map((r, i) => {
                            const isSource = r.source === selectedNodeId
                            const partnerId = isSource ? r.target : r.source
                            const partner = graphData?.nodes.find((n) => n.id === partnerId)
                            if (!partner) return null
                            return (
                              <button
                                key={i}
                                onClick={() => setSelectedNodeId(partnerId)}
                                className="group flex w-full items-center justify-between rounded-lg border border-border bg-muted/20 p-2 text-left text-xs transition-colors hover:bg-accent hover:text-accent-foreground"
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="truncate text-[9px] font-semibold text-orange-500">
                                    {isSource ? "leads to ->" : "<- relates from"}
                                  </div>
                                  <div className="mt-0.5 truncate font-medium text-foreground group-hover:text-primary">
                                    {partner.label}
                                  </div>
                                </div>
                                <ChevronRightIcon className="ml-2 size-3.5 text-muted-foreground group-hover:text-foreground" />
                              </button>
                            )
                          })}
                        </FieldContent>
                      </Field>
                    ) : null}
                  </FieldGroup>
                </ScrollArea>
              </div>
            </Sheet>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// MindMapCanvasNode – custom node component.
// Reads toggle/select actions from context so it never captures stale closures
// and React Flow never sees a data reference change from a callback update.
// ---------------------------------------------------------------------------

function MindMapCanvasNode({ id, data }: NodeProps<MindMapFlowNode>) {
  const { toggle } = useMindMapActions()

  const rootClasses =
    "border-slate-300 bg-slate-100 text-slate-900 shadow-[0_14px_35px_-18px_rgba(15,23,42,0.45)] dark:border-slate-700 dark:bg-slate-900/90 dark:text-slate-50"
  const mainClasses =
    "border-blue-200 bg-blue-50 text-blue-950 shadow-[0_12px_28px_-18px_rgba(37,99,235,0.5)] dark:border-blue-900/60 dark:bg-blue-950/50 dark:text-blue-100"
  const subClasses =
    "border-emerald-200 bg-emerald-50 text-emerald-950 shadow-[0_10px_24px_-20px_rgba(5,150,105,0.45)] dark:border-emerald-900/60 dark:bg-emerald-950/35 dark:text-emerald-100"

  return (
    <>
      <Handle
        type="target"
        position={FlowPosition.Left}
        className={HIDDEN_HANDLE_CLASS}
        isConnectable={false}
      />
      <div
        title={data.label}
        className={cn(
          "flex h-full w-full items-center gap-2.5 rounded-2xl border px-3 py-3 text-left transition-all duration-200",
          data.variant === "root" && rootClasses,
          data.variant === "main" && mainClasses,
          data.variant === "sub" && subClasses,
          data.highlightState === "highlighted" && "ring-2 ring-yellow-400/45",
          data.highlightState === "dimmed" && "opacity-20 hover:opacity-100",
          data.variant !== "sub" && "hover:-translate-y-0.5"
        )}
      >
        <div className="min-w-0 flex-1">
          <div
            className={cn(
              "line-clamp-2 leading-snug font-semibold",
              data.variant === "root" && "text-[14px]",
              data.variant === "main" && "text-[12.5px]",
              data.variant === "sub" && "line-clamp-3 text-[11px]"
            )}
          >
            {data.label}
          </div>
          {data.description && data.variant !== "sub" && (
            <div className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-muted-foreground">
              {data.description}
            </div>
          )}
        </div>

        {data.canToggle ? (
          <button
            type="button"
            className={cn(
              "nodrag nopan cursor-pointer flex size-6 shrink-0 items-center justify-center rounded-full border transition-colors",
              data.variant === "root" &&
                "border-slate-300 bg-white/70 text-slate-700 hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200",
              data.variant === "main" &&
                "border-blue-300 bg-white/70 text-blue-700 hover:bg-blue-100 dark:border-blue-700 dark:bg-blue-900/50 dark:text-blue-200"
            )}
            aria-label={data.isExpanded ? "Collapse node" : "Expand node"}
            onPointerDown={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation()
              toggle(id)
            }}
          >
            <ChevronRightIcon
              className={cn(
                "size-3.5 transition-transform",
                data.isExpanded && "rotate-90"
              )}
            />
          </button>
        ) : (
          <div className="flex size-6 shrink-0 items-center justify-center rounded-full border border-emerald-300 bg-white/70 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-200">
            <ChevronRightIcon className="size-3.5" />
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={FlowPosition.Right}
        className={HIDDEN_HANDLE_CLASS}
        isConnectable={false}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// MindMapFlowCanvas – wraps ReactFlow and provides the actions context.
// A stable ref wrapper ensures the context value never changes identity,
// so custom nodes don't re-render unnecessarily when callbacks change.
// ---------------------------------------------------------------------------

function MindMapFlowCanvas({
  open,
  notebookName,
  layout,
  flowNodes,
  flowEdges,
  activeMapId,
  selectedNodeId,
  setSelectedNodeId,
  pendingFocusNodeIds,
  setPendingFocusNodeIds,
  searchQuery,
  setSearchQuery,
  graphData,
  onGenerateNew,
  onToggleNode,
  onSelectNode,
}: {
  open: boolean
  notebookName: string
  layout: LayoutResult | null
  flowNodes: MindMapFlowNode[]
  flowEdges: MindMapFlowEdge[]
  activeMapId: string | null
  selectedNodeId: string | null
  setSelectedNodeId: React.Dispatch<React.SetStateAction<string | null>>
  pendingFocusNodeIds: string[] | null
  setPendingFocusNodeIds: React.Dispatch<React.SetStateAction<string[] | null>>
  searchQuery: string
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>
  graphData: MindMapContent | null
  onGenerateNew?: () => void
  onToggleNode: (nodeId: string) => void
  onSelectNode: (nodeId: string) => void
}) {
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })

  // Local node state allows React Flow to track drag positions.
  // Sync from the computed flowNodes whenever the layout changes (expand/collapse resets positions).
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<MindMapFlowNode>(flowNodes)
  useEffect(() => {
    setRfNodes(flowNodes)
  }, [flowNodes, setRfNodes])

  const resizeObserverRef = useRef<ResizeObserver | null>(null)
  const reactFlowRef = useRef<ReactFlowInstance<MindMapFlowNode, MindMapFlowEdge> | null>(null)
  const flowCanvasRef = useRef<HTMLDivElement | null>(null)
  const lastFitMapIdRef = useRef<string | null>(null)
  const lastDimensionsRef = useRef({ width: 800, height: 600 })

  // Ref that always holds the latest toggle callback.
  // The stable actions object delegates to this ref so the context value
  // never changes reference.
  const toggleRef = useRef(onToggleNode)

  // Update ref in layout effect to avoid updating refs during render
  React.useLayoutEffect(() => {
    toggleRef.current = onToggleNode
  }, [onToggleNode])

  // Stable MindMapActions object — same reference for the lifetime of this
  // component. Context consumers won't re-render when callbacks change.
  const stableActions = useMemo<MindMapActions>(() => ({
    toggle: (id) => toggleRef.current(id),
  }), [])

  const containerRef = useCallback((node: HTMLDivElement | null) => {
    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect()
      resizeObserverRef.current = null
    }
    if (!node) return

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) setDimensions({ width, height })
      }
    })
    ro.observe(node)
    resizeObserverRef.current = ro
  }, [])

  const fitToNodes = useCallback(
    (nodeIds?: string[]) => {
      const instance = reactFlowRef.current
      if (!instance || flowNodes.length === 0) return

      const isMobile = dimensions.width < 640
      const targets = nodeIds?.length
        ? flowNodes.filter((n) => nodeIds.includes(n.id))
        : flowNodes
      if (!targets.length) return

      void instance.fitView({
        nodes: targets,
        padding: isMobile ? 0.22 : 0.35,
        duration: 450,
        minZoom: isMobile ? 0.55 : 0.25,
        maxZoom: 1.15,
      })
    },
    [dimensions.width, flowNodes]
  )

  const resetView = useCallback(() => {
    void reactFlowRef.current?.setViewport({ x: 0, y: 0, zoom: 1 }, { duration: 260 })
  }, [])

  const zoomIn = useCallback(() => {
    void reactFlowRef.current?.zoomIn({ duration: 220 })
  }, [])

  const zoomOut = useCallback(() => {
    void reactFlowRef.current?.zoomOut({ duration: 220 })
  }, [])

  // Auto-fit when map or container dimensions change
  useEffect(() => {
    if (!open) {
      lastFitMapIdRef.current = null
      return
    }
    const dimensionsChangedFromDefault =
      lastDimensionsRef.current.width === 800 && dimensions.width !== 800

    if (
      flowNodes.length > 0 &&
      (lastFitMapIdRef.current !== (activeMapId ?? "new") || dimensionsChangedFromDefault)
    ) {
      const t = window.setTimeout(() => {
        fitToNodes()
        lastFitMapIdRef.current = activeMapId ?? "new"
        lastDimensionsRef.current = { ...dimensions }
      }, 120)
      return () => window.clearTimeout(t)
    }
  }, [activeMapId, dimensions, fitToNodes, flowNodes.length, open])

  // Fit to pending focus nodes after expand/collapse
  useEffect(() => {
    if (!pendingFocusNodeIds?.length) return
    const t = window.setTimeout(() => {
      fitToNodes(pendingFocusNodeIds)
      setPendingFocusNodeIds(null)
    }, 60)
    return () => window.clearTimeout(t)
  }, [fitToNodes, pendingFocusNodeIds, setPendingFocusNodeIds])

  // Focus selected node
  useEffect(() => {
    if (!selectedNodeId || pendingFocusNodeIds?.length || !graphData?.nodes?.length) return
    const node = graphData.nodes.find((n) => n.id === selectedNodeId)
    if (!node) return

    const isMobile = dimensions.width < 640
    const focusIds = [selectedNodeId]
    if (node.type === "sub" && node.parentId) {
      focusIds.push(node.parentId)
    } else if (!isMobile && node.type === "main") {
      const root = graphData.nodes.find((n) => n.type === "root") ?? graphData.nodes[0]
      if (root) focusIds.push(root.id)
    }

    const t = window.setTimeout(() => fitToNodes(focusIds), 80)
    return () => window.clearTimeout(t)
  }, [dimensions.width, fitToNodes, graphData, pendingFocusNodeIds, selectedNodeId])

  // -------------------------------------------------------------------------
  // Export helpers
  // -------------------------------------------------------------------------

  const handleExportJSON = useCallback(() => {
    if (!graphData) return
    const blob = new Blob([JSON.stringify(graphData, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${notebookName.toLowerCase().replace(/\s+/g, "-")}-mindmap.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success("Mind map exported to JSON.")
  }, [graphData, notebookName])

  const handleExportPNG = useCallback(async () => {
    if (!flowCanvasRef.current) return
    try {
      const dataUrl = await toPng(flowCanvasRef.current, {
        cacheBust: true,
        pixelRatio: 2,
        backgroundColor: getComputedStyle(document.body).backgroundColor,
      })
      const a = document.createElement("a")
      a.href = dataUrl
      a.download = `${notebookName.toLowerCase().replace(/\s+/g, "-")}-mindmap.png`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      toast.success("Mind map exported to PNG.")
    } catch (err) {
      console.error("Failed to export PNG:", err)
      toast.error("Failed to export PNG.")
    }
  }, [notebookName])

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div ref={containerRef} className="relative min-h-0 flex-1 bg-background">
      {layout ? (
        <>
          <div ref={flowCanvasRef} className="absolute inset-0">
            {/* Provide stable actions context before ReactFlow so custom nodes
                can call toggle/select without stale closures */}
            <MindMapActionsCtx.Provider value={stableActions}>
              <ReactFlow<MindMapFlowNode, MindMapFlowEdge>
                nodes={rfNodes}
                edges={flowEdges}
                nodeTypes={NODE_TYPES}
                onInit={(instance) => {
                  reactFlowRef.current = instance
                }}
                onNodesChange={(changes: NodeChange<MindMapFlowNode>[]) => onNodesChange(changes)}
                onPaneClick={() => setSelectedNodeId(null)}
                onNodeClick={(_, node) => onSelectNode(node.id)}
                nodesDraggable={true}
                nodesConnectable={false}
                elementsSelectable={true}
                selectNodesOnDrag={false}
                panOnDrag={dimensions.width < 640 ? true : [1, 2]}
                minZoom={0.15}
                maxZoom={3}
                zoomOnDoubleClick={false}
                proOptions={{ hideAttribution: true }}
                className="bg-background"
                defaultEdgeOptions={{ interactionWidth: 24 }}
              >
                <Background
                  variant={BackgroundVariant.Dots}
                  gap={24}
                  size={1.6}
                  color="rgba(120,120,120,0.18)"
                />
              </ReactFlow>
            </MindMapActionsCtx.Provider>
          </div>

          {/* Search bar */}
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between p-4">
            <div className="pointer-events-auto w-36 sm:w-64">
              <div className="relative">
                <SearchIcon className="absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={dimensions.width < 640 ? "Search..." : "Search concepts..."}
                  className="h-9 w-full border-border bg-background/95 pr-8 pl-9 text-xs text-foreground shadow-lg backdrop-blur focus-visible:ring-primary"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute top-1/2 right-2 flex size-5 -translate-y-1/2 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <XIcon className="size-3" />
                  </button>
                )}
              </div>
            </div>

            <div className="pointer-events-auto flex items-center gap-1.5 sm:gap-2">
              <Button
                onClick={handleExportJSON}
                size="sm"
                variant="outline"
                className="h-9 gap-1.5 border-border bg-background/90 px-2.5 text-xs text-foreground hover:bg-muted sm:px-3"
              >
                <FileJsonIcon className="size-3.5 text-emerald-500" />
                <span className="hidden sm:inline">Export JSON</span>
              </Button>
              <Button
                onClick={handleExportPNG}
                size="sm"
                variant="outline"
                className="h-9 gap-1.5 border-border bg-background/90 px-2.5 text-xs text-foreground hover:bg-muted sm:px-3"
              >
                <ImageIcon className="size-3.5 text-blue-500" />
                <span className="hidden sm:inline">Export PNG</span>
              </Button>
            </div>
          </div>

          {/* Zoom controls */}
          <div className="pointer-events-none absolute inset-x-0 bottom-4 left-4 z-10 flex">
            <div className="pointer-events-auto flex gap-1 rounded-lg border border-border bg-background/90 p-1 shadow-lg backdrop-blur">
              <TooltipIconButton icon={<ZoomInIcon className="size-4" />} onClick={zoomIn} label="Zoom In" />
              <TooltipIconButton icon={<ZoomOutIcon className="size-4" />} onClick={zoomOut} label="Zoom Out" />
              <TooltipIconButton icon={<Maximize2Icon className="size-4" />} onClick={() => fitToNodes()} label="Fit Canvas" />
              <TooltipIconButton icon={<Minimize2Icon className="size-4" />} onClick={resetView} label="Reset View" />
            </div>
          </div>
        </>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
          <div className="max-w-sm rounded-lg border border-border bg-card p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-foreground">
              Mind map data is incomplete
            </h3>
            <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              This saved output does not contain renderable nodes. Generate a new
              mind map or open another saved version.
            </p>
            {onGenerateNew ? (
              <Button
                variant="outline"
                size="sm"
                onClick={onGenerateNew}
                className="mt-4 h-8 text-xs"
              >
                Generate New
              </Button>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// TooltipIconButton
// ---------------------------------------------------------------------------

function TooltipIconButton({
  icon,
  onClick,
  label,
}: {
  icon: React.ReactNode
  onClick: () => void
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className="flex size-7 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      title={label}
      aria-label={label}
    >
      {icon}
    </button>
  )
}
