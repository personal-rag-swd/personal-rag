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
  initialMap,
  isGenerating,
  onGenerate,
}: {
  notebookId: string;
  notebookName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialMap?: NotebookReport | null;
  isGenerating: boolean;
  onGenerate: (detailLevel: "simple" | "intermediate" | "detailed", instructions: string) => void;
}) {
  const [detailLevel, setDetailLevel] = useState<"simple" | "intermediate" | "detailed">("intermediate");
  const [instructions, setInstructions] = useState("");
  
  // Custom selections
  const [selectedMap, setSelectedMap] = useState<NotebookReport | null>(() =>
    initialMap?.reportType === "mindmap" ? initialMap : null
  );
  const [userIsGeneratingNew, setUserIsGeneratingNew] = useState<boolean | null>(() =>
    initialMap?.reportType === "mindmap" ? false : null
  );

  const [isRootExpanded, setIsRootExpanded] = useState(false);
  const [expandedMainNodeIds, setExpandedMainNodeIds] = useState<Set<string>>(new Set());
  const [pendingFocusNodeIds, setPendingFocusNodeIds] = useState<string[] | null>(null);

  // Graph canvas dimension and pan/zoom state
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const containerElementRef = useRef<HTMLDivElement | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  const containerRef = useCallback((node: HTMLDivElement | null) => {
    containerElementRef.current = node;

    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect();
      resizeObserverRef.current = null;
    }

    if (node) {
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const w = entry.contentRect.width;
          const h = entry.contentRect.height;
          if (w > 0 && h > 0) {
            setDimensions({ width: w, height: h });
          }
        }
      });
      resizeObserver.observe(node);
      resizeObserverRef.current = resizeObserver;
    }
  }, []);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const panStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const activePointerIdRef = useRef<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const { data: reports } = useNotebookReportsQuery(notebookId);
  const lastFitMapIdRef = useRef<string | null>(null);

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

  const activeMapId = activeMap?.id ?? null;
  const prevActiveMapIdRef = useRef<string | null>(activeMapId);

  useEffect(() => {
    if (activeMapId === prevActiveMapIdRef.current) {
      return;
    }

    prevActiveMapIdRef.current = activeMapId;
    setIsRootExpanded(false);
    setExpandedMainNodeIds(new Set());
    setPendingFocusNodeIds(null);
  }, [activeMapId]);

  useEffect(() => {
    lastFitMapIdRef.current = null;
  }, [activeMapId]);

  // Derived state: isGeneratingNew is true if user requested it, or if there are no existing maps
  const isGeneratingNew = useMemo(() => {
    if (isGenerating) return true;
    if (userIsGeneratingNew !== null) return userIsGeneratingNew;
    return mindMaps.length === 0;
  }, [userIsGeneratingNew, mindMaps, isGenerating]);

  // Dimensions are tracked reactively via the containerRef callback ref

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
    onGenerate(detailLevel, instructions);
  };

  // Drag to Pan logic using PointerEvents for seamless mouse and touch support
  const handlePointerDown = (e: React.PointerEvent) => {
    // For pointer events, left click for mouse; touch/stylus have e.button === 0 or -1 (no buttons)
    if (e.button !== 0 && e.pointerType === "mouse") return;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    panStartRef.current = { ...pan };
    activePointerIdRef.current = e.pointerId;
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!dragStartRef.current) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;

    if (!isDragging) {
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance > 5) {
        setIsDragging(true);
        if (activePointerIdRef.current !== null) {
          try {
            e.currentTarget.setPointerCapture(activePointerIdRef.current);
          } catch (err) {
            console.warn("Failed to capture pointer:", err);
          }
        }
      } else {
        return; // Don't drag yet
      }
    }

    setPan({
      x: panStartRef.current.x + dx,
      y: panStartRef.current.y + dy,
    });
  };

  const handlePointerUpOrLeave = (e: React.PointerEvent) => {
    dragStartRef.current = null;
    activePointerIdRef.current = null;
    if (isDragging) {
      setIsDragging(false);
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        // ignore
      }
    }
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

    const mainNodes = isRootExpanded
      ? nodes.filter((n) => n.type === "main" && n.id !== rootNode.id)
      : [];
    const subNodes = isRootExpanded
      ? nodes.filter((n) => n.type === "sub" && expandedMainNodeIds.has(n.parentId || ""))
      : [];

    const rightMain = mainNodes;
    const leftMain: MindMapNode[] = [];

    const positions: Record<string, Position> = {};

    // Base dimensions for nodes
    const nodeWidths = { root: 260, main: 230, sub: 200 };
    const nodeHeights = { root: 100, main: 85, sub: 70 };

    const xSpacing = 330;
    const subYSpacing = 85;
    const mainGap = 65;

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
  }, [graphData, isRootExpanded, expandedMainNodeIds]);

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

  const focusOnNodes = useCallback((nodeIds: string[]) => {
    if (!layout || !containerElementRef.current) return;
    const coords = nodeIds
      .map((id) => layout.positions[id])
      .filter(Boolean);

    if (coords.length === 0) return;

    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;

    coords.forEach((pos) => {
      minX = Math.min(minX, pos.x);
      maxX = Math.max(maxX, pos.x + pos.width);
      minY = Math.min(minY, pos.y);
      maxY = Math.max(maxY, pos.y + pos.height);
    });

    const graphWidth = maxX - minX;
    const graphHeight = maxY - minY;

    const containerWidth = dimensions.width;
    const containerHeight = dimensions.height;

    const isMobileSize = containerWidth < 640;
    const padding = isMobileSize ? 30 : 120;
    const scaleX = (containerWidth - padding) / graphWidth;
    const scaleY = (containerHeight - padding) / graphHeight;
    let nextScale = Math.min(Math.min(scaleX, scaleY), 1.25);

    // Enforce readable scale for mobile path focus (at least 0.55x)
    if (isMobileSize) {
      nextScale = Math.max(nextScale, 0.55);
    }

    const graphCenterX = minX + graphWidth / 2;
    const graphCenterY = minY + graphHeight / 2;

    setZoom(nextScale);
    setPan({
      x: -graphCenterX * nextScale,
      y: -graphCenterY * nextScale,
    });
  }, [layout, dimensions]);

  const expandRoot = () => {
    setIsRootExpanded(true);
    if (graphData?.nodes) {
      const rootNode = graphData.nodes.find((n) => n.type === "root") || graphData.nodes[0];
      const mainNodes = graphData.nodes.filter((n) => n.type === "main" && n.id !== rootNode.id);
      if (rootNode) {
        setPendingFocusNodeIds([rootNode.id, ...mainNodes.map((m) => m.id)]);
      }
    }
  };

  const collapseRoot = () => {
    if (graphData?.nodes) {
      const rootNode = graphData.nodes.find((n) => n.type === "root") || graphData.nodes[0];
      if (rootNode) {
        setIsRootExpanded(false);
        setExpandedMainNodeIds(new Set());
        setPendingFocusNodeIds([rootNode.id]);
      }
    }
  };

  const expandMainNode = (mId: string) => {
    setExpandedMainNodeIds((prev) => {
      const next = new Set(prev);
      next.add(mId);
      return next;
    });
    if (graphData?.nodes) {
      const isMobile = dimensions.width < 640;
      if (isMobile) {
        const childIds = graphData.nodes.filter((n) => n.parentId === mId).map((n) => n.id);
        setPendingFocusNodeIds([mId, ...childIds]);
      } else {
        const rootNode = graphData.nodes.find((n) => n.type === "root") || graphData.nodes[0];
        if (rootNode) {
          setPendingFocusNodeIds([mId, rootNode.id]);
        }
      }
    }
  };

  const collapseMainNode = (mId: string) => {
    setExpandedMainNodeIds((prev) => {
      const next = new Set(prev);
      next.delete(mId);
      return next;
    });
    if (graphData?.nodes) {
      const isMobile = dimensions.width < 640;
      if (isMobile) {
        setPendingFocusNodeIds([mId]);
      } else {
        const rootNode = graphData.nodes.find((n) => n.type === "root") || graphData.nodes[0];
        if (rootNode) {
          setPendingFocusNodeIds([mId, rootNode.id]);
        }
      }
    }
  };

  // Trigger focus transition when layout updates and pendingFocusNodeIds is present
  useEffect(() => {
    if (layout && pendingFocusNodeIds) {
      const timer = setTimeout(() => {
        focusOnNodes(pendingFocusNodeIds);
        setPendingFocusNodeIds(null);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [layout, pendingFocusNodeIds, focusOnNodes]);

  // Trigger focus when selectedNodeId changes (only if layout doesn't need to update first)
  useEffect(() => {
    if (!selectedNodeId || !graphData || !layout) return;
    if (pendingFocusNodeIds) return;

    const node = graphData.nodes.find((n) => n.id === selectedNodeId);
    if (!node) return;

    const isMobile = dimensions.width < 640;
    const focusIds: string[] = [selectedNodeId];
    if (isMobile) {
      if (node.type === "sub" && node.parentId) {
        focusIds.push(node.parentId);
      }
    } else {
      if (node.type === "sub" && node.parentId) {
        focusIds.push(node.parentId);
      } else if (node.type === "main") {
        const rootNode = graphData.nodes.find((n) => n.type === "root") || graphData.nodes[0];
        if (rootNode) {
          focusIds.push(rootNode.id);
        }
      }
    }

    const timer = setTimeout(() => {
      focusOnNodes(focusIds);
    }, 50);
    return () => clearTimeout(timer);
  }, [selectedNodeId, focusOnNodes, graphData, layout, pendingFocusNodeIds, dimensions.width]);

  // Fit to screen helper: computes bounding box of layout and centers it
  const fitToView = useCallback(() => {
    if (!layout || !containerElementRef.current) return;
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

    const containerWidth = dimensions.width;
    const containerHeight = dimensions.height;

    const isMobileSize = containerWidth < 640;
    const padding = isMobileSize ? 30 : 80;
    const scaleX = (containerWidth - padding) / graphWidth;
    const scaleY = (containerHeight - padding) / graphHeight;
    let nextScale = Math.min(Math.min(scaleX, scaleY), 1.2);

    // Enforce readable scale on mobile initial render (at least 0.55x)
    if (isMobileSize) {
      nextScale = Math.max(nextScale, 0.55);
    }

    const graphCenterX = minX + graphWidth / 2;
    const graphCenterY = minY + graphHeight / 2;

    setZoom(nextScale);
    setPan({
      x: -graphCenterX * nextScale,
      y: -graphCenterY * nextScale,
    });
  }, [layout, dimensions]);

  // Track last measured dimensions to trigger fitToView if the viewport updates from default
  const lastDimensionsRef = useRef({ width: 800, height: 600 });

  // Fit view when layout changes or dimensions initialize/change (only once per map session)
  useEffect(() => {
    if (!open) {
      lastFitMapIdRef.current = null;
      return;
    }
    const dimensionsChangedFromDefault =
      lastDimensionsRef.current.width === 800 && dimensions.width !== 800;

    if (
      layout &&
      dimensions.width > 0 &&
      (lastFitMapIdRef.current !== (activeMap?.id || "new") || dimensionsChangedFromDefault)
    ) {
      const timer = setTimeout(() => {
        fitToView();
        lastFitMapIdRef.current = activeMap?.id || "new";
        lastDimensionsRef.current = { ...dimensions };
      }, 120);
      return () => clearTimeout(timer);
    }
  }, [layout, open, dimensions, activeMap?.id, fitToView]);

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
        className="flex flex-col p-0 gap-0 fixed top-0 left-0 translate-x-0 translate-y-0 sm:top-1/2 sm:left-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 w-full max-w-none sm:max-w-[min(100%-2rem,1400px)] h-dvh sm:h-[min(100%-4rem,90vh)] overflow-hidden bg-background border-none sm:border border-border text-foreground sm:rounded-xl"
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-3 pt-[calc(env(safe-area-inset-top,0px)+0.875rem)] pb-3.5 sm:px-5 sm:py-3.5 border-b border-border shrink-0 bg-muted/40">
          <div className="min-w-0 flex-1">
            <DialogTitle className="text-sm sm:text-base font-semibold text-foreground flex items-center gap-2 min-w-0">
              <span className="bg-primary/20 text-primary px-1.5 sm:px-2 py-0.5 rounded text-[10px] sm:text-xs border border-primary/30 shrink-0">
                Mind Map
              </span>
              <span className="truncate">{notebookName}</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground mt-0.5 truncate hidden sm:block">
              {activeMap
                ? `Active: Generated ${formatDistanceToNow(new Date(activeMap.createdAt), { addSuffix: true })}`
                : "Generate a concept network from your notebook materials."}
            </DialogDescription>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            {mindMaps.length > 0 && !isGeneratingNew && (
               <select
                 value={activeMap?.id || ""}
                 onChange={(e) => {
                   const map = mindMaps.find((m) => m.id === e.target.value);
                   if (map) setSelectedMap(map);
                 }}
                 className="max-w-[85px] sm:max-w-none bg-background border border-border text-xs rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary text-foreground truncate"
               >
                {mindMaps.map((m, idx) => (
                  <option key={m.id} value={m.id}>
                    V{mindMaps.length - idx} ({formatDistanceToNow(new Date(m.createdAt), { addSuffix: true })})
                  </option>
                ))}
              </select>
            )}

            {!isGeneratingNew && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setUserIsGeneratingNew(true)}
                className="h-8 text-xs border-border hover:bg-muted text-foreground gap-1 px-2 sm:px-3 shrink-0"
              >
                <PlusIcon className="size-3.5" />
                <span className="hidden sm:inline">Generate New</span>
              </Button>
            )}

            <button
              onClick={() => onOpenChange(false)}
              className="flex size-8 items-center justify-center rounded bg-muted border border-border hover:bg-accent text-muted-foreground hover:text-foreground transition-colors cursor-pointer shrink-0"
              aria-label="Close dialog"
            >
              <XIcon className="size-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        {isGeneratingNew ? (
          <div className="flex-1 min-h-0 flex flex-col md:flex-row bg-background">
            {/* Generate Setup Panel */}
            <div className="w-full md:w-96 border-r border-border p-6 flex flex-col shrink-0 overflow-y-auto bg-card">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-5 flex items-center gap-1.5">
                <SparklesIcon className="size-4 text-primary animate-pulse" />
                Generate Settings
              </h2>

              <div className="space-y-5 flex-1">
                {/* Detail Level */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-foreground">
                    Depth / Level of Detail
                  </label>
                  <ToggleGroup
                    disabled={isGenerating}
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
                      className="px-3 py-1.5 text-xs rounded border-border data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
                    >
                      Simple
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="intermediate"
                      className="px-3 py-1.5 text-xs rounded border-border data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
                    >
                      Intermediate
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="detailed"
                      className="px-3 py-1.5 text-xs rounded border-border data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
                    >
                      Detailed
                    </ToggleGroupItem>
                  </ToggleGroup>
                  <p className="text-[10px] text-muted-foreground mt-1 leading-relaxed">
                    {detailLevel === "simple" && "Generates high-level outline: 3-5 main branches and 5-10 sub-concepts."}
                    {detailLevel === "intermediate" && "Balanced representation: 5-8 main branches and 10-20 sub-concepts."}
                    {detailLevel === "detailed" && "Deep knowledge graph: 8-12 main branches and 20-35 sub-concepts."}
                  </p>
                </div>

                {/* Additional instructions */}
                <div className="space-y-2">
                  <label className="text-xs font-medium text-foreground">
                    Focus Instructions (Optional)
                  </label>
                  <Textarea
                    disabled={isGenerating}
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    placeholder="Focus on specific topics (e.g. 'Concentrate on deployment procedures and MinIO configs')"
                    rows={8}
                    className="bg-background border-border focus-visible:ring-primary text-xs resize-none text-foreground"
                  />
                </div>
              </div>

              {/* Generate Trigger */}
              <div className="pt-4 border-t border-border space-y-2">
                <Button
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="w-full gap-2 text-xs py-5 rounded-lg"
                >
                  {isGenerating ? (
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
                    disabled={isGenerating}
                    onClick={() => setUserIsGeneratingNew(false)}
                    className="w-full text-xs text-muted-foreground hover:text-foreground"
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </div>

            {/* Explanatory Panel / Graphic mock */}
            <div className="flex-1 bg-muted/20 p-8 flex flex-col items-center justify-center text-center">
              {isGenerating ? (
                <>
                  <div className="size-16 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary mb-4 animate-pulse">
                    <Loader2Icon className="size-8 animate-spin" />
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">
                    Generating Mind Map...
                  </h3>
                  <p className="text-xs text-muted-foreground max-w-sm mt-1.5 leading-relaxed">
                    Please wait while we scan your documents and build the knowledge network. You can close this dialog; the process will continue in the background.
                  </p>
                </>
              ) : (
                <>
                  <div className="size-16 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary mb-4 animate-pulse">
                    <SparklesIcon className="size-8" />
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">
                    Visualize Document Relationships
                  </h3>
                  <p className="text-xs text-muted-foreground max-w-sm mt-1.5 leading-relaxed">
                    Personal RAG automatically scans files parsed into your notebook, extracts core subjects, organizes sub-branches, and drafts relationships.
                  </p>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 min-h-0 flex bg-background relative overflow-hidden">
            {/* Interactive Graph Canvas */}
            <div
              ref={containerRef}
              className="flex-1 min-h-0 relative select-none cursor-grab active:cursor-grabbing bg-background touch-none"
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUpOrLeave}
              onPointerCancel={handlePointerUpOrLeave}
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
                    <circle cx="2" cy="2" r="1.2" fill="rgba(120,120,120,0.15)" />
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
                    className={cn(
                      "transition-transform ease-out duration-300",
                      isDragging ? "transition-none" : ""
                    )}
                  >
                    {/* 1. Connection lines (Bezier links converging to central junctions) */}
                    {(() => {
                      const rootNode = layout.rootNode;
                      const rootPos = layout.positions[rootNode.id];
                      if (!rootPos || !isRootExpanded) return null;

                      const rootStartX = rootPos.x + rootPos.width;
                      const rootStartY = rootPos.y + rootPos.height / 2;
                      const junctionX = rootStartX + 45;

                      return (
                        <>
                          {/* Horizontal line from root to junction */}
                          <path
                            d={`M ${rootStartX} ${rootStartY} L ${junctionX} ${rootStartY}`}
                            className="fill-none stroke-blue-500/35"
                            strokeWidth="2"
                          />

                          {/* Junction Circle with '<' for root */}
                          <g
                            transform={`translate(${junctionX}, ${rootStartY})`}
                            className="group cursor-pointer"
                            onClick={(e) => {
                              e.stopPropagation();
                              collapseRoot();
                            }}
                          >
                            <circle
                              r="20"
                              className="fill-transparent stroke-none"
                            />
                            <circle
                              r="10"
                              className="fill-background stroke-blue-500/60 group-hover:stroke-blue-500 group-hover:fill-blue-500/10 transition-colors"
                              strokeWidth="1.5"
                            />
                            <text
                              y="3.5"
                              className="text-[11px] font-bold fill-blue-500 select-none pointer-events-none group-hover:fill-blue-600"
                              textAnchor="middle"
                            >
                              &lt;
                            </text>
                          </g>

                          {/* Render horizontal lines and circles for each expanded main node */}
                          {layout.mainNodes
                            .filter((m) => expandedMainNodeIds.has(m.id))
                            .map((m) => {
                              const mPos = layout.positions[m.id];
                              if (!mPos) return null;

                              const startX = mPos.x + mPos.width;
                              const startY = mPos.y + mPos.height / 2;
                              const mainJunctionX = startX + 35;

                              return (
                                <g key={`junction-${m.id}`}>
                                  {/* Line from main node to its junction */}
                                  <path
                                    d={`M ${startX} ${startY} L ${mainJunctionX} ${startY}`}
                                    className="fill-none stroke-blue-500/35"
                                    strokeWidth="2"
                                  />
                                  {/* Junction Circle with '<' for main node */}
                                  <g
                                    transform={`translate(${mainJunctionX}, ${startY})`}
                                    className="group cursor-pointer"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      collapseMainNode(m.id);
                                    }}
                                  >
                                    <circle
                                      r="20"
                                      className="fill-transparent stroke-none"
                                    />
                                    <circle
                                      r="10"
                                      className="fill-background stroke-emerald-500/60 group-hover:stroke-emerald-500 group-hover:fill-emerald-500/10 transition-colors"
                                      strokeWidth="1.5"
                                    />
                                    <text
                                      y="3.5"
                                      className="text-[11px] font-bold fill-emerald-500 select-none pointer-events-none group-hover:fill-emerald-600"
                                      textAnchor="middle"
                                    >
                                      &lt;
                                    </text>
                                  </g>
                                </g>
                              );
                            })}

                          {/* Render curves between nodes */}
                          {Object.entries(layout.positions).map(([nodeId, pos]) => {
                            const node = graphData?.nodes.find((n) => n.id === nodeId);
                            if (!node || !node.parentId || nodeId === layout.rootNode.id) return null;

                            const isMainNode = node.parentId === layout.rootNode.id;

                            if (isMainNode) {
                              // Curves from root junction to main nodes
                              const endX = pos.x;
                              const endY = pos.y + pos.height / 2;
                              const midX = (junctionX + endX) / 2;
                              const pathD = `M ${junctionX} ${rootStartY} C ${midX} ${rootStartY}, ${midX} ${endY}, ${endX} ${endY}`;

                              return (
                                <path
                                  key={`link-${nodeId}`}
                                  d={pathD}
                                  className="fill-none stroke-blue-500/35 hover:stroke-blue-500/70 transition-all duration-200"
                                  strokeWidth="2"
                                />
                              );
                            } else {
                              // Curves from main junction to sub nodes
                              const parentPos = layout.positions[node.parentId];
                              if (!parentPos) return null;

                              const startX = parentPos.x + parentPos.width;
                              const startY = parentPos.y + parentPos.height / 2;
                              const mainJunctionX = startX + 35;

                              const endX = pos.x;
                              const endY = pos.y + pos.height / 2;
                              const midX = (mainJunctionX + endX) / 2;
                              const pathD = `M ${mainJunctionX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;

                              return (
                                <path
                                  key={`link-${nodeId}`}
                                  d={pathD}
                                  className="fill-none stroke-blue-500/35 hover:stroke-blue-500/70 transition-all duration-200"
                                  strokeWidth="2"
                                />
                              );
                            }
                          })}
                        </>
                      );
                    })()}

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

                    {/* 3. Horizontal layout concept nodes */}
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
                              if (node.type === "root" && !isRootExpanded) {
                                expandRoot();
                              } else if (node.type === "main" && !expandedMainNodeIds.has(nodeId)) {
                                expandMainNode(nodeId);
                              }
                            }}
                            title={node.label}
                            className={cn(
                              "w-full h-full p-2.5 rounded-lg border flex flex-col justify-center transition-all duration-200 cursor-pointer shadow-md select-none",
                              // Root node styles
                              node.type === "root" &&
                                "bg-violet-100 dark:bg-violet-950/60 border-violet-300 dark:border-violet-800 text-violet-900 dark:text-violet-100 font-bold",
                              // Main nodes styles
                              node.type === "main" &&
                                "bg-blue-100 dark:bg-blue-950/60 border-blue-300 dark:border-blue-800 text-blue-900 dark:text-blue-100",
                              // Sub nodes styles
                              node.type === "sub" &&
                                "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/60 text-emerald-900 dark:text-emerald-100",
                              // Highlights
                              isSelected && "border-primary ring-2 ring-primary/30",
                              highlightState === "highlighted" &&
                                "border-yellow-500/60 ring-2 ring-yellow-500/20",
                              highlightState === "dimmed" && "opacity-20 hover:opacity-100"
                            )}
                          >
                            <div className="flex items-center justify-between gap-2.5 w-full h-full">
                              <div className="flex-1 min-w-0">
                                {/* Node labels */}
                                <div
                                  className={cn(
                                    "font-medium leading-snug select-none",
                                    node.type === "root"
                                      ? "text-violet-900 dark:text-violet-100 text-[13px] font-bold line-clamp-2"
                                      : node.type === "sub"
                                        ? "text-emerald-900 dark:text-emerald-100 text-[11px] font-medium line-clamp-3"
                                        : "text-blue-900 dark:text-blue-100 text-[12px] font-semibold line-clamp-2"
                                  )}
                                >
                                  {node.label}
                                </div>
                                {/* Branch type badge & short excerpt */}
                                {node.description && node.type !== "sub" && (
                                  <div className="text-[9px] text-muted-foreground mt-0.5 line-clamp-1 select-none">
                                    {node.description}
                                  </div>
                                )}
                              </div>
                              {node.type === "main" && !expandedMainNodeIds.has(node.id) && (
                                <div
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    expandMainNode(node.id);
                                  }}
                                  className="size-5 rounded-full bg-blue-500/10 dark:bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-blue-500 hover:bg-blue-500 hover:text-white transition-all text-[10px] font-bold shrink-0 cursor-pointer"
                                >
                                  &gt;
                                </div>
                              )}
                              {node.type === "sub" && (
                                <div
                                  className="size-5 rounded-full bg-emerald-500/10 dark:bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-500 text-[10px] font-bold shrink-0"
                                >
                                  &gt;
                                </div>
                              )}
                            </div>
                          </div>
                        </foreignObject>
                      );
                    })}

                    {/* Root Node Expand button (only when collapsed) */}
                    {!isRootExpanded && layout && (
                      <g
                        transform={`translate(${layout.positions[layout.rootNode.id].x + layout.positions[layout.rootNode.id].width + 15}, 0)`}
                        className="group cursor-pointer"
                        onClick={(e) => {
                          e.stopPropagation();
                          expandRoot();
                        }}
                      >
                        <circle
                          r="22"
                          className="fill-transparent stroke-none"
                        />
                        <circle
                          r="12"
                          className="fill-primary stroke-primary/30 group-hover:stroke-primary group-hover:brightness-110 transition-all"
                          strokeWidth="2"
                        />
                        <text
                          y="4"
                          className="text-[13px] font-bold fill-primary-foreground select-none pointer-events-none"
                          textAnchor="middle"
                        >
                          &gt;
                        </text>
                      </g>
                    )}
                  </g>
                </svg>
              )}

              {!layout && (
                <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
                  <div className="max-w-sm rounded-lg border border-border bg-card p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-foreground">
                      Mind map data is incomplete
                    </h3>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                      This saved output does not contain renderable nodes. Generate a new mind map or open another saved version.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setUserIsGeneratingNew(true)}
                      className="mt-4 h-8 text-xs"
                    >
                      Generate New
                    </Button>
                  </div>
                </div>
              )}

              {/* Overlay Canvas Controls */}
              {layout && (
                <div className="absolute left-4 bottom-4 flex flex-col gap-2 pointer-events-auto">
                <div className="flex bg-background/90 backdrop-blur border border-border rounded-lg p-1 gap-1 shadow-lg">
                  <TooltipIconButton icon={<ZoomInIcon className="size-4" />} onClick={zoomIn} label="Zoom In" />
                  <TooltipIconButton icon={<ZoomOutIcon className="size-4" />} onClick={zoomOut} label="Zoom Out" />
                  <TooltipIconButton icon={<Maximize2Icon className="size-4" />} onClick={fitToView} label="Fit Canvas" />
                  <TooltipIconButton icon={<Minimize2Icon className="size-4" />} onClick={resetView} label="Reset View" />
                </div>
                </div>
              )}

              {/* Search Control Overlay */}
              <div className="absolute left-4 top-4 pointer-events-auto w-36 sm:w-64">
                <div className="relative">
                  <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={dimensions.width < 640 ? "Search..." : "Search concepts..."}
                    className="bg-background/95 backdrop-blur border-border text-xs pl-9 pr-8 h-9 shadow-lg focus-visible:ring-primary w-full text-foreground"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 size-5 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted rounded cursor-pointer"
                    >
                      <XIcon className="size-3" />
                    </button>
                  )}
                </div>
              </div>

              {/* Export Panel Overlay */}
              <div className="absolute right-4 top-4 pointer-events-auto flex items-center gap-1.5 sm:gap-2">
                <Button
                  onClick={handleExportJSON}
                  size="sm"
                  variant="outline"
                  className="bg-background/90 border-border hover:bg-muted text-foreground text-xs gap-1.5 h-9 px-2.5 sm:px-3"
                >
                  <FileJsonIcon className="size-3.5 text-emerald-500" />
                  <span className="hidden sm:inline">Export JSON</span>
                </Button>
                <Button
                  onClick={handleExportSVG}
                  size="sm"
                  variant="outline"
                  className="bg-background/90 border-border hover:bg-muted text-foreground text-xs gap-1.5 h-9 px-2.5 sm:px-3"
                >
                  <ImageIcon className="size-3.5 text-blue-500" />
                  <span className="hidden sm:inline">Export SVG</span>
                </Button>
              </div>
            </div>

            {/* Backdrop for mobile details drawer */}
            {selectedNode && (
              <div
                className="absolute inset-0 bg-background/50 backdrop-blur-xs sm:hidden z-10 cursor-pointer"
                onClick={() => setSelectedNodeId(null)}
              />
            )}

            {/* Concept details Drawer Panel */}
            {selectedNode && (
              <div className="absolute right-0 top-0 bottom-0 w-[85vw] max-w-sm sm:w-80 sm:relative sm:border-l border-border bg-card flex flex-col shrink-0 overflow-hidden animate-in slide-in-from-right duration-250 z-20 shadow-2xl sm:shadow-none">
                <div className="flex items-center justify-between px-4 py-3.5 border-b border-border bg-muted/40">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Concept Details
                  </span>
                  <button
                    onClick={() => setSelectedNodeId(null)}
                    className="size-6 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors cursor-pointer"
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
                      <h3 className="text-sm font-bold text-foreground mt-2 leading-snug">
                        {selectedNode.label}
                      </h3>
                    </div>

                    {/* Node Definition / Content Description */}
                    <div className="space-y-1">
                      <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                        Summary & Definition
                      </h4>
                      <p className="text-xs text-foreground leading-relaxed bg-muted/40 rounded border border-border p-3 whitespace-pre-wrap select-text">
                        {selectedNode.description || "No description provided for this concept."}
                      </p>
                    </div>

                    {/* Symmetrical jump connections */}
                    {selectedNodeRelationships.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
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
                                className="group flex w-full items-center justify-between p-2 rounded text-left bg-muted/20 border border-border hover:bg-accent hover:text-accent-foreground transition-colors text-xs"
                              >
                                <div className="min-w-0 flex-1">
                                  <div className="text-[9px] text-orange-500 font-semibold truncate">
                                    {isSource ? `leads to →` : `← relates from`}
                                  </div>
                                  <div className="font-medium text-foreground group-hover:text-primary truncate mt-0.5">
                                    {partner.label}
                                  </div>
                                </div>
                                <ChevronRightIcon className="size-3.5 text-muted-foreground group-hover:text-foreground ml-2" />
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
      className="size-7 flex items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
      title={label}
      aria-label={label}
    >
      {icon}
    </button>
  );
}
