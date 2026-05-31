import * as React from "react";
import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import {
  ChevronRightIcon,
  FileJsonIcon,
  ImageIcon,
  Loader2Icon,
  Maximize2Icon,
  Minimize2Icon,
  PlusIcon,
  SearchIcon,
  SparklesIcon,
  XIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

import {
  useGenerateNotebookReportMutation,
  useNotebookReportsQuery,
} from "@/features/notebooks/api";
import type {
  NotebookReport,
  MindMapContent,
  MindMapNode,
} from "@/features/notebooks/types";

type Position = { x: number; y: number; width: number; height: number };

export function MindMapDialog({
  notebookId,
  notebookName,
  open,
  onOpenChange,
}: {
  notebookId: string;
  notebookName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [detailLevel, setDetailLevel] = useState<"simple" | "intermediate" | "detailed">("intermediate");
  const [instructions, setInstructions] = useState("");
  
  // Custom selections
  const [selectedMap, setSelectedMap] = useState<NotebookReport | null>(null);
  const [userIsGeneratingNew, setUserIsGeneratingNew] = useState<boolean | null>(null);

  // Graph canvas dimension and pan/zoom state
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const panStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  const { data: reports } = useNotebookReportsQuery(notebookId);
  const generateMutation = useGenerateNotebookReportMutation(notebookId);

  // Filter mindmap reports
  const mindMaps = useMemo(() => {
    if (!reports) return [];
    return reports.filter((r) => r.reportType === "mindmap");
  }, [reports]);

  // Derived state: activeMap is either the user selected map, or falls back to the latest map
  const activeMap = useMemo(() => {
    if (selectedMap) return selectedMap;
    if (mindMaps.length > 0) return mindMaps[0];
    return null;
  }, [selectedMap, mindMaps]);

  // Derived state: isGeneratingNew is true if user requested it, or if there are no existing maps
  const isGeneratingNew = useMemo(() => {
    if (userIsGeneratingNew !== null) return userIsGeneratingNew;
    return mindMaps.length === 0;
  }, [userIsGeneratingNew, mindMaps]);

  // Handle ResizeObserver to track container sizes reactively without ref accesses in render
  useEffect(() => {
    if (!open) return;
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width || 800,
          height: entry.contentRect.height || 600,
        });
      }
    });

    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, [open]);

  // Handle SVG Zooming on mouse wheel
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const zoomFactor = 0.08;
      setZoom((prev) => {
        const next = e.deltaY < 0 ? prev + zoomFactor : prev - zoomFactor;
        return Math.min(Math.max(next, 0.15), 3);
      });
    };

    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      svg.removeEventListener("wheel", handleWheel);
    };
  }, [activeMap]);

  const handleGenerate = () => {
    generateMutation.mutate(
      {
        reportType: "mindmap",
        additionalInstructions: instructions.trim() || undefined,
        detailLevel,
      },
      {
        onSuccess: (report) => {
          toast.success("Mind map generated successfully!");
          setSelectedMap(report);
          setUserIsGeneratingNew(false);
          setInstructions("");
        },
        onError: (error) => {
          toast.error(`Failed to generate mind map: ${error.message}`);
        },
      }
    );
  };

  // Drag to Pan logic
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click drag
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    panStartRef.current = { ...pan };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !dragStartRef.current) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    setPan({
      x: panStartRef.current.x + dx,
      y: panStartRef.current.y + dy,
    });
  };

  const handleMouseUpOrLeave = () => {
    setIsDragging(false);
    dragStartRef.current = null;
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const zoomIn = () => setZoom((z) => Math.min(z + 0.15, 3));
  const zoomOut = () => setZoom((z) => Math.max(z - 0.15, 0.15));

  // Extract mind map structure from the report
  const graphData = useMemo(() => {
    if (!activeMap) return null;
    return activeMap.content as MindMapContent;
  }, [activeMap]);

  // Compute node layouts dynamically
  const layout = useMemo(() => {
    if (!graphData || !graphData.nodes) return null;

    const nodes = graphData.nodes;
    const rootNode = nodes.find((n) => n.type === "root") || nodes[0];
    if (!rootNode) return null;

    const mainNodes = nodes.filter((n) => n.type === "main" && n.id !== rootNode.id);
    const subNodes = nodes.filter((n) => n.type === "sub");

    const rightMain = mainNodes.filter((_, idx) => idx % 2 === 0);
    const leftMain = mainNodes.filter((_, idx) => idx % 2 === 1);

    const positions: Record<string, Position> = {};

    // Base dimensions for nodes
    const nodeWidths = { root: 220, main: 190, sub: 160 };
    const nodeHeights = { root: 85, main: 70, sub: 50 };

    const xSpacing = 280;
    const subYSpacing = 65;
    const mainGap = 50;

    // Helper to calculate height of a main branch subtree
    const getSubtreeHeight = (children: MindMapNode[]) => {
      return Math.max(1, children.length) * subYSpacing;
    };

    // Calculate positions for one side (left or right)
    const positionSide = (mainNodesList: MindMapNode[], isRight: boolean) => {
      const xDirection = isRight ? 1 : -1;

      // 1. Calculate heights
      const branchHeights: Record<string, number> = {};
      let totalHeight = 0;

      mainNodesList.forEach((m) => {
        const children = subNodes.filter((s) => s.parentId === m.id);
        const h = getSubtreeHeight(children);
        branchHeights[m.id] = h;
        totalHeight += h;
      });

      if (mainNodesList.length > 1) {
        totalHeight += (mainNodesList.length - 1) * mainGap;
      }

      // 2. Position branches
      let currentY = -totalHeight / 2;

      mainNodesList.forEach((m) => {
        const children = subNodes.filter((s) => s.parentId === m.id);
        const subtreeHeight = branchHeights[m.id];
        const mY = currentY + subtreeHeight / 2;
        const mX = xDirection * xSpacing;

        positions[m.id] = {
          x: mX - nodeWidths.main / 2,
          y: mY - nodeHeights.main / 2,
          width: nodeWidths.main,
          height: nodeHeights.main,
        };

        // Position sub-branches
        children.forEach((s, idx) => {
          const sX = xDirection * 2 * xSpacing;
          const sY = mY + (idx - (children.length - 1) / 2) * subYSpacing;

          positions[s.id] = {
            x: sX - nodeWidths.sub / 2,
            y: sY - nodeHeights.sub / 2,
            width: nodeWidths.sub,
            height: nodeHeights.sub,
          };
        });

        currentY += subtreeHeight + mainGap;
      });
    };

    // Center root
    positions[rootNode.id] = {
      x: -nodeWidths.root / 2,
      y: -nodeHeights.root / 2,
      width: nodeWidths.root,
      height: nodeHeights.root,
    };

    // Compute left and right
    positionSide(rightMain, true);
    positionSide(leftMain, false);

    return {
      positions,
      rootNode,
      mainNodes,
      subNodes,
      rightMain,
      leftMain,
    };
  }, [graphData]);

  // Selected node info
  const selectedNode = useMemo(() => {
    if (!graphData || !selectedNodeId) return null;
    return graphData.nodes.find((n) => n.id === selectedNodeId) || null;
  }, [graphData, selectedNodeId]);

  // Selected node's relationships
  const selectedNodeRelationships = useMemo(() => {
    if (!graphData || !selectedNodeId) return [];
    return (graphData.relationships || []).filter(
      (r) => r.source === selectedNodeId || r.target === selectedNodeId
    );
  }, [graphData, selectedNodeId]);

  // Fit to screen helper: computes bounding box of layout and centers it
  const fitToView = useCallback(() => {
    if (!layout || !containerRef.current) return;
    const p = layout.positions;
    const coords = Object.values(p);
    if (coords.length === 0) return;

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;

    coords.forEach((node) => {
      minX = Math.min(minX, node.x);
      maxX = Math.max(maxX, node.x + node.width);
      minY = Math.min(minY, node.y);
      maxY = Math.max(maxY, node.y + node.height);
    });

    const graphWidth = maxX - minX;
    const graphHeight = maxY - minY;

    const containerWidth = containerRef.current.clientWidth || 800;
    const containerHeight = containerRef.current.clientHeight || 600;

    const scaleX = (containerWidth - 80) / graphWidth;
    const scaleY = (containerHeight - 80) / graphHeight;
    const nextScale = Math.min(Math.min(scaleX, scaleY), 1.2);

    const graphCenterX = minX + graphWidth / 2;
    const graphCenterY = minY + graphHeight / 2;

    setZoom(nextScale);
    setPan({
      x: containerWidth / 2 - graphCenterX * nextScale,
      y: containerHeight / 2 - graphCenterY * nextScale,
    });
  }, [layout]);

  // Fit view when layout changes
  useEffect(() => {
    if (layout) {
      const timer = setTimeout(fitToView, 50);
      return () => clearTimeout(timer);
    }
  }, [layout, fitToView]);

  // Export as JSON
  const handleExportJSON = () => {
    if (!graphData) return;
    const dataStr = JSON.stringify(graphData, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${notebookName.toLowerCase().replace(/\s+/g, "-")}-mindmap.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("Mind map exported to JSON!");
  };

  // Export as SVG file
  const handleExportSVG = () => {
    const svgElement = svgRef.current;
    if (!svgElement || !layout) return;

    // Find bounding box
    const p = layout.positions;
    const coords = Object.values(p);
    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;

    coords.forEach((node) => {
      minX = Math.min(minX, node.x);
      maxX = Math.max(maxX, node.x + node.width);
      minY = Math.min(minY, node.y);
      maxY = Math.max(maxY, node.y + node.height);
    });

    const width = maxX - minX + 160;
    const height = maxY - minY + 160;
    const viewX = minX - 80;
    const viewY = minY - 80;

    // Create standalone SVG content
    const clone = svgElement.cloneNode(true) as SVGSVGElement;
    clone.setAttribute("viewBox", `${viewX} ${viewY} ${width} ${height}`);
    clone.setAttribute("width", width.toString());
    clone.setAttribute("height", height.toString());

    // Clean up dynamic UI elements like control overlays in exported file
    const rootG = clone.querySelector("g");
    if (rootG) {
      rootG.removeAttribute("transform"); // Remove live pan/zoom transform
    }

    // Embed inline styles to make it self-contained
    const styles = `
      svg { font-family: Inter, system-ui, sans-serif; background-color: #0b0f19; color: #fff; }
      .edge { stroke: #2563eb; stroke-width: 1.5px; fill: none; opacity: 0.6; }
      .rel-edge { stroke: #ea580c; stroke-width: 1.5px; stroke-dasharray: 4,4; fill: none; opacity: 0.8; }
      .node-card { fill: #1e293b; stroke: #334155; stroke-width: 1.5px; rx: 8px; }
      .node-card-root { fill: #1e3a8a; stroke: #3b82f6; stroke-width: 2px; rx: 12px; }
      .node-card-main { fill: #1e293b; stroke: #2563eb; stroke-width: 1.5px; rx: 8px; }
      .node-card-sub { fill: #0f172a; stroke: #475569; stroke-dasharray: 0; stroke-width: 1px; rx: 6px; }
      .node-text { fill: #ffffff; font-size: 13px; font-weight: 500; font-family: sans-serif; }
      .node-text-title { font-weight: 700; font-size: 15px; }
      .node-text-sub { font-size: 11px; fill: #94a3b8; }
    `;
    const styleElement = document.createElement("style");
    styleElement.textContent = styles;
    clone.insertBefore(styleElement, clone.firstChild);

    // Convert clone to XML
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(clone);
    const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = `${notebookName.toLowerCase().replace(/\s+/g, "-")}-mindmap.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success("Mind map exported to SVG!");
  };

  // Node highlight checker based on search query
  const getHighlightState = (label: string, desc?: string | null) => {
    if (!searchQuery.trim()) return "normal";
    const text = `${label} ${desc || ""}`.toLowerCase();
    const term = searchQuery.toLowerCase();
    if (text.includes(term)) return "highlighted";
    return "dimmed";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="flex flex-col p-0 gap-0 max-w-[95vw] w-[1400px] h-[90vh] overflow-hidden bg-slate-950 border-slate-800 text-slate-100 rounded-xl"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-3.5 border-b border-slate-800 shrink-0 bg-slate-900/50">
          <div className="min-w-0 flex-1">
            <DialogTitle className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <span className="bg-primary/20 text-primary px-2 py-0.5 rounded text-xs border border-primary/30">
                Mind Map
              </span>
              <span>{notebookName}</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-400 mt-0.5 truncate">
              {activeMap
                ? `Active: Generated ${formatDistanceToNow(new Date(activeMap.createdAt), { addSuffix: true })}`
                : "Generate a concept network from your notebook materials."}
            </DialogDescription>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {mindMaps.length > 0 && !isGeneratingNew && (
              <select
                value={activeMap?.id || ""}
                onChange={(e) => {
                  const map = mindMaps.find((m) => m.id === e.target.value);
                  if (map) setSelectedMap(map);
                }}
                className="bg-slate-800 border border-slate-700 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary text-slate-200"
              >
                {mindMaps.map((m, idx) => (
                  <option key={m.id} value={m.id}>
                    Version {mindMaps.length - idx} ({formatDistanceToNow(new Date(m.createdAt), { addSuffix: true })})
                  </option>
                ))}
              </select>
            )}

            {!isGeneratingNew && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setUserIsGeneratingNew(true)}
                className="h-8 text-xs border-slate-700 hover:bg-slate-800 text-slate-200 gap-1.5"
              >
                <PlusIcon className="size-3.5" />
                Generate New
              </Button>
            )}

            <button
              onClick={() => onOpenChange(false)}
              className="flex size-8 items-center justify-center rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-400 hover:text-slate-100 transition-colors cursor-pointer"
              aria-label="Close dialog"
            >
              <XIcon className="size-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        {isGeneratingNew ? (
          <div className="flex-1 min-h-0 flex flex-col md:flex-row bg-slate-950">
            {/* Generate Setup Panel */}
            <div className="w-full md:w-96 border-r border-slate-800 p-6 flex flex-col shrink-0 overflow-y-auto">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-5 flex items-center gap-1.5">
                <SparklesIcon className="size-4 text-primary animate-pulse" />
                Generate Settings
              </h2>

              <div className="space-y-5 flex-1">
                {/* Detail Level */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-300">
                    Depth / Level of Detail
                  </label>
                  <ToggleGroup
                    value={[detailLevel]}
                    onValueChange={(val: string[]) => {
                      if (val[0] === "simple" || val[0] === "intermediate" || val[0] === "detailed") {
                        setDetailLevel(val[0]);
                      }
                    }}
                    variant="outline"
                    className="justify-start gap-2"
                  >
                    <ToggleGroupItem
                      value="simple"
                      className="px-3 py-1.5 text-xs rounded border-slate-700 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
                    >
                      Simple
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="intermediate"
                      className="px-3 py-1.5 text-xs rounded border-slate-700 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
                    >
                      Intermediate
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="detailed"
                      className="px-3 py-1.5 text-xs rounded border-slate-700 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
                    >
                      Detailed
                    </ToggleGroupItem>
                  </ToggleGroup>
                  <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
                    {detailLevel === "simple" && "Generates high-level outline: 3-5 main branches and 5-10 sub-concepts."}
                    {detailLevel === "intermediate" && "Balanced representation: 5-8 main branches and 10-20 sub-concepts."}
                    {detailLevel === "detailed" && "Deep knowledge graph: 8-12 main branches and 20-35 sub-concepts."}
                  </p>
                </div>

                {/* Additional instructions */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-300">
                    Focus Instructions (Optional)
                  </label>
                  <Textarea
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    placeholder="Focus on specific topics (e.g. 'Concentrate on deployment procedures and MinIO configs')"
                    rows={8}
                    className="bg-slate-900 border-slate-700 focus-visible:ring-primary text-xs resize-none"
                  />
                </div>
              </div>

              {/* Generate Trigger */}
              <div className="pt-4 border-t border-slate-800 space-y-2">
                <Button
                  onClick={handleGenerate}
                  disabled={generateMutation.isPending}
                  className="w-full gap-2 text-xs py-5 rounded-lg"
                >
                  {generateMutation.isPending ? (
                    <>
                      <Loader2Icon className="size-4 animate-spin" />
                      Generating Knowledge Graph...
                    </>
                  ) : (
                    <>
                      <SparklesIcon className="size-4" />
                      Generate Mind Map
                    </>
                  )}
                </Button>

                {mindMaps.length > 0 && (
                  <Button
                    variant="ghost"
                    onClick={() => setUserIsGeneratingNew(false)}
                    className="w-full text-xs text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </div>

            {/* Explanatory Panel / Graphic mock */}
            <div className="flex-1 bg-slate-900/20 p-8 flex flex-col items-center justify-center text-center">
              <div className="size-16 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary mb-4 animate-pulse">
                <SparklesIcon className="size-8" />
              </div>
              <h3 className="text-sm font-semibold text-slate-200">
                Visualize Document Relationships
              </h3>
              <p className="text-xs text-slate-400 max-w-sm mt-1.5 leading-relaxed">
                Personal RAG automatically scans files parsed into your notebook, extracts core subjects, organizes sub-branches, and drafts relationships.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex-1 min-h-0 flex bg-slate-950 relative overflow-hidden">
            {/* Interactive Graph Canvas */}
            <div
              ref={containerRef}
              className="flex-1 min-h-0 relative select-none cursor-grab active:cursor-grabbing bg-[#0b0f19]"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUpOrLeave}
              onMouseLeave={handleMouseUpOrLeave}
            >
              {/* Grid dots pattern background */}
              <svg className="absolute inset-0 size-full pointer-events-none">
                <defs>
                  <pattern
                    id="grid-dots"
                    width="24"
                    height="24"
                    patternUnits="userSpaceOnUse"
                  >
                    <circle cx="2" cy="2" r="1.2" fill="rgba(255,255,255,0.06)" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid-dots)" />
              </svg>

              {/* Live Render SVG */}
              {layout && (
                <svg
                  ref={svgRef}
                  className="size-full absolute inset-0 pointer-events-auto"
                >
                  <defs>
                    {/* Relationship Arrowhead Markers */}
                    <marker
                      id="arrow"
                      viewBox="0 0 10 10"
                      refX="6"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#ea580c" />
                    </marker>

                    <linearGradient id="gradient-right" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity="0.4" />
                    </linearGradient>

                    <linearGradient id="gradient-left" x1="100%" y1="0%" x2="0%" y2="0%">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity="0.4" />
                    </linearGradient>
                  </defs>

                  <g
                    transform={`translate(${dimensions.width / 2 + pan.x}, ${dimensions.height / 2 + pan.y}) scale(${zoom})`}
                  >
                    {/* 1. Connection lines (Bezier links) */}
                    {Object.entries(layout.positions).map(([nodeId, pos]) => {
                      const node = graphData?.nodes.find((n) => n.id === nodeId);
                      if (!node || !node.parentId || nodeId === layout.rootNode.id) return null;

                      const parentPos = layout.positions[node.parentId];
                      if (!parentPos) return null;

                      const isRight = pos.x > 0;

                      // Source point (parent card edge)
                      const startX = isRight
                        ? parentPos.x + parentPos.width
                        : parentPos.x;
                      const startY = parentPos.y + parentPos.height / 2;

                      // Target point (child card edge)
                      const endX = isRight ? pos.x : pos.x + pos.width;
                      const endY = pos.y + pos.height / 2;

                      const midX = (startX + endX) / 2;
                      const pathD = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;

                      return (
                        <path
                          key={`link-${nodeId}`}
                          d={pathD}
                          className="fill-none stroke-blue-500/35 hover:stroke-blue-500/70 transition-all duration-200"
                          strokeWidth="2"
                        />
                      );
                    })}

                    {/* 2. Cross-branch relationships */}
                    {(graphData?.relationships || []).map((rel, idx) => {
                      const srcPos = layout.positions[rel.source];
                      const tgtPos = layout.positions[rel.target];
                      if (!srcPos || !tgtPos) return null;

                      // Start and end from centers
                      const startX = srcPos.x + srcPos.width / 2;
                      const startY = srcPos.y + srcPos.height / 2;
                      const endX = tgtPos.x + tgtPos.width / 2;
                      const endY = tgtPos.y + tgtPos.height / 2;

                      const dx = endX - startX;
                      const dy = endY - startY;
                      const dr = Math.sqrt(dx * dx + dy * dy);

                      // Bow path slightly
                      const pathD = `M ${startX} ${startY} A ${dr} ${dr} 0 0 1 ${endX} ${endY}`;

                      return (
                        <g key={`rel-${idx}`} className="group/rel">
                          <path
                            d={pathD}
                            className="fill-none stroke-orange-500/60 hover:stroke-orange-500 stroke-dasharray-4 cursor-pointer transition-all duration-200"
                            strokeWidth="2.5"
                            markerEnd="url(#arrow)"
                          />
                          {/* Relationship label */}
                          <foreignObject
                            x={(startX + endX) / 2 - 60}
                            y={(startY + endY) / 2 - 10}
                            width="120"
                            height="24"
                            className="overflow-visible pointer-events-none"
                          >
                            <div className="bg-orange-950/90 text-[10px] text-orange-400 font-semibold px-2 py-0.5 rounded border border-orange-500/30 text-center select-none truncate">
                              {rel.label}
                            </div>
                          </foreignObject>
                        </g>
                      );
                    })}

                    {/* 3. Symmetrical layout concept nodes */}
                    {Object.entries(layout.positions).map(([nodeId, pos]) => {
                      const node = graphData?.nodes.find((n) => n.id === nodeId);
                      if (!node) return null;

                      const isSelected = selectedNodeId === nodeId;
                      const highlightState = getHighlightState(node.label, node.description);

                      return (
                        <foreignObject
                          key={`node-${nodeId}`}
                          x={pos.x}
                          y={pos.y}
                          width={pos.width}
                          height={pos.height}
                          className="overflow-visible select-none pointer-events-auto"
                        >
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedNodeId(nodeId);
                            }}
                            className={cn(
                              "w-full h-full p-2.5 rounded-lg border flex flex-col justify-center transition-all duration-200 cursor-pointer shadow-md select-none",
                              // Root node styles
                              node.type === "root" &&
                                "bg-slate-900 border-blue-500/80 ring-2 ring-blue-500/20 hover:scale-105",
                              // Main nodes styles
                              node.type === "main" &&
                                "bg-slate-900 border-slate-700 hover:border-blue-500 hover:scale-[1.03]",
                              // Sub nodes styles
                              node.type === "sub" &&
                                "bg-slate-950 border-slate-800 hover:border-slate-600 hover:scale-[1.03]",
                              // Highlights
                              isSelected && "border-primary ring-2 ring-primary/30",
                              highlightState === "highlighted" &&
                                "border-yellow-500/60 ring-2 ring-yellow-500/20",
                              highlightState === "dimmed" && "opacity-20 hover:opacity-100"
                            )}
                          >
                            {/* Node labels */}
                            <div
                              className={cn(
                                "font-medium text-slate-100 leading-snug line-clamp-2 select-none",
                                node.type === "root" ? "text-[12px] font-bold text-blue-400" : "text-[11px]"
                              )}
                            >
                              {node.label}
                            </div>
                            {/* Branch type badge & short excerpt */}
                            {node.description && node.type !== "sub" && (
                              <div className="text-[9px] text-slate-400 mt-0.5 line-clamp-1 select-none">
                                {node.description}
                              </div>
                            )}
                          </div>
                        </foreignObject>
                      );
                    })}
                  </g>
                </svg>
              )}

              {/* Overlay Canvas Controls */}
              <div className="absolute left-4 bottom-4 flex flex-col gap-2 pointer-events-auto">
                <div className="flex bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg p-1 gap-1 shadow-lg">
                  <TooltipIconButton icon={<ZoomInIcon className="size-4" />} onClick={zoomIn} label="Zoom In" />
                  <TooltipIconButton icon={<ZoomOutIcon className="size-4" />} onClick={zoomOut} label="Zoom Out" />
                  <TooltipIconButton icon={<Maximize2Icon className="size-4" />} onClick={fitToView} label="Fit Canvas" />
                  <TooltipIconButton icon={<Minimize2Icon className="size-4" />} onClick={resetView} label="Reset View" />
                </div>
              </div>

              {/* Search Control Overlay */}
              <div className="absolute left-4 top-4 pointer-events-auto w-64">
                <div className="relative">
                  <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-slate-400" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search concepts..."
                    className="bg-slate-900/95 backdrop-blur border-slate-800 text-xs pl-8.5 pr-8 h-9 shadow-lg focus-visible:ring-primary w-full text-slate-200"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 size-5 flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded cursor-pointer"
                    >
                      <XIcon className="size-3" />
                    </button>
                  )}
                </div>
              </div>

              {/* Export Panel Overlay */}
              <div className="absolute right-4 top-4 pointer-events-auto flex items-center gap-2">
                <Button
                  onClick={handleExportJSON}
                  size="sm"
                  variant="outline"
                  className="bg-slate-900/90 border-slate-800 hover:bg-slate-800 hover:border-slate-700 text-xs gap-1.5 h-9"
                >
                  <FileJsonIcon className="size-3.5 text-emerald-500" />
                  Export JSON
                </Button>
                <Button
                  onClick={handleExportSVG}
                  size="sm"
                  variant="outline"
                  className="bg-slate-900/90 border-slate-800 hover:bg-slate-800 hover:border-slate-700 text-xs gap-1.5 h-9"
                >
                  <ImageIcon className="size-3.5 text-blue-500" />
                  Export SVG
                </Button>
              </div>
            </div>

            {/* Concept details Drawer Panel */}
            {selectedNode && (
              <div className="w-80 border-l border-slate-800 bg-slate-900/50 flex flex-col shrink-0 overflow-hidden relative animate-in slide-in-from-right duration-250 z-10">
                <div className="flex items-center justify-between px-4 py-3.5 border-b border-slate-800 bg-slate-900/70">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Concept Details
                  </span>
                  <button
                    onClick={() => setSelectedNodeId(null)}
                    className="size-6 flex items-center justify-center text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors cursor-pointer"
                  >
                    <XIcon className="size-3.5" />
                  </button>
                </div>

                <ScrollArea className="flex-1 min-h-0">
                  <div className="p-4 space-y-5">
                    {/* Node Label */}
                    <div>
                      <span className="text-[10px] bg-blue-950 text-blue-400 border border-blue-900 font-semibold px-2 py-0.5 rounded uppercase">
                        {selectedNode.type === "root" && "Central Topic"}
                        {selectedNode.type === "main" && "Core Concept"}
                        {selectedNode.type === "sub" && "Concept Detail"}
                      </span>
                      <h3 className="text-sm font-bold text-slate-100 mt-2 leading-snug">
                        {selectedNode.label}
                      </h3>
                    </div>

                    {/* Node Definition / Content Description */}
                    <div className="space-y-1">
                      <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                        Summary & Definition
                      </h4>
                      <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 rounded border border-slate-800/80 p-3 whitespace-pre-wrap select-text">
                        {selectedNode.description || "No description provided for this concept."}
                      </p>
                    </div>

                    {/* Symmetrical jump connections */}
                    {selectedNodeRelationships.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                          Concept Relationships
                        </h4>
                        <div className="space-y-1.5">
                          {selectedNodeRelationships.map((rel, idx) => {
                            const isSource = rel.source === selectedNodeId;
                            const partnerId = isSource ? rel.target : rel.source;
                            const partner = graphData?.nodes.find((n) => n.id === partnerId);
                            if (!partner) return null;

                            return (
                              <button
                                key={idx}
                                onClick={() => setSelectedNodeId(partnerId)}
                                className="group flex w-full items-center justify-between p-2 rounded text-left bg-slate-950/30 border border-slate-800 hover:bg-slate-800/50 hover:border-slate-700 transition-colors text-xs"
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="text-[9px] text-orange-400 font-semibold truncate">
                                    {isSource ? `leads to →` : `← relates from`}
                                  </div>
                                  <div className="font-medium text-slate-200 group-hover:text-primary truncate mt-0.5">
                                    {partner.label}
                                  </div>
                                </div>
                                <ChevronRightIcon className="size-3.5 text-slate-500 group-hover:text-slate-300 ml-2" />
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// Micro Helper components
function TooltipIconButton({
  icon,
  onClick,
  label,
}: {
  icon: React.ReactNode;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className="size-7 flex items-center justify-center rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer"
      title={label}
      aria-label={label}
    >
      {icon}
    </button>
  );
}
