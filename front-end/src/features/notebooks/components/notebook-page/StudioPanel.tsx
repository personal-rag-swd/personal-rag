import { useState } from "react"
import {
  FileTextIcon,
  Loader2Icon,
  PanelRightCloseIcon,
  PanelRightOpenIcon,
  PlusIcon,
  AlertCircleIcon,
  CircleOffIcon,
  Trash2Icon,
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"

import { Button } from "@/components/ui/button"
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
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import {
  useNotebookReportsQuery,
  useDeleteNotebookReportMutation,
} from "@/features/notebooks/api"
import type { NotebookReport } from "@/features/notebooks/types"

import { STUDIO_ACTIONS } from "./studioActions"
import { REPORT_TYPE_BY_ID } from "./reportTypes"

export function StudioPanel({
  notebookId,
  isCollapsed,
  onToggleCollapse,
  onActivate,
  activeFeature,
  onViewReport,
  isMindMapGenerating,
}: {
  notebookId?: string
  isCollapsed?: boolean
  onToggleCollapse?: () => void
  onActivate?: (actionId: string) => void
  activeFeature?: string | null
  onViewReport?: (report: NotebookReport) => void
  isMindMapGenerating?: boolean
}) {
  const { data: reports, isLoading: isReportsLoading } =
    useNotebookReportsQuery(notebookId)

  const showSavedOutputs =
    (reports && reports.length > 0) || isMindMapGenerating

  function renderReportIcon(report: NotebookReport) {
    if (report.status === "pending" || report.status === "generating") {
      return <Loader2Icon className="size-3.5 animate-spin" />
    }
    if (report.status === "failed") {
      return <AlertCircleIcon className="size-3.5 text-destructive" />
    }
    if (report.status === "cancelled") {
      return <CircleOffIcon className="size-3.5 text-muted-foreground/60" />
    }
    const meta = REPORT_TYPE_BY_ID[report.reportType]
    return meta?.icon ?? <FileTextIcon className="size-3.5" />
  }

  function renderReportDescription(report: NotebookReport) {
    if (report.status === "pending") {
      return "Queued..."
    }
    if (report.status === "generating") {
      return <span className="animate-pulse">Generating...</span>
    }
    if (report.status === "failed") {
      return (
        <span className="text-destructive">
          {report.errorMessage ?? "Generation failed"}
        </span>
      )
    }
    if (report.status === "cancelled") {
      return "Cancelled"
    }
    return formatDistanceToNow(new Date(report.createdAt), {
      addSuffix: true,
    })
  }

  const isReportInProgress = (report: NotebookReport) =>
    report.status === "pending" || report.status === "generating"

  return (
    <div
      className={cn(
        "flex h-full min-h-0 flex-col bg-card transition-all duration-300",
        isCollapsed ? "w-14 shrink-0 items-center justify-between py-2" : ""
      )}
    >
      {isCollapsed ? (
        <>
          <div className="flex w-full flex-col items-center gap-3">
            <Tooltip>
              <TooltipTrigger
                onClick={onToggleCollapse}
                className="flex size-8 items-center justify-center rounded-2xl text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Expand panel"
              >
                <PanelRightOpenIcon className="size-4" />
              </TooltipTrigger>
              <TooltipContent side="left">Expand panel</TooltipContent>
            </Tooltip>

            <div className="min-h-0 w-full flex-1 overflow-y-auto [&::-webkit-scrollbar]:hidden [& scrollbar-width-none]">
              <div className="flex flex-col items-center gap-2.5 px-2">
                {STUDIO_ACTIONS.map((action) => {
                  const ActionIcon = action.icon
                  return (
                    <Tooltip key={action.id}>
                      <TooltipTrigger
                        onClick={() => onActivate?.(action.id)}
                        className={cn(
                          "flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-lg border transition-all duration-200 hover:scale-105",
                          activeFeature === action.id
                            ? "border-primary bg-primary/10 text-primary"
                            : "bg-muted text-muted-foreground hover:text-foreground"
                        )}
                        aria-label={action.label}
                      >
                        <ActionIcon className="size-4" />
                      </TooltipTrigger>
                      <TooltipContent side="left">
                        {action.label}
                      </TooltipContent>
                    </Tooltip>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="flex w-full flex-col items-center px-2">
            <Tooltip>
              <TooltipTrigger
                className="flex size-9 items-center justify-center rounded-full border bg-background text-muted-foreground shadow-sm transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Add note"
              >
                <PlusIcon className="size-4" />
              </TooltipTrigger>
              <TooltipContent side="left">Add note</TooltipContent>
            </Tooltip>
          </div>
        </>
      ) : (
        <>
          {/* Action buttons grid — fixed at top */}
          <div className="p-3">
            <div className="grid grid-cols-2 gap-2">
              {STUDIO_ACTIONS.map((action) => {
                const ActionIcon = action.icon
                const isDisabled = !action.implemented
                return (
                  <button
                    key={action.id}
                    onClick={() => !isDisabled && onActivate?.(action.id)}
                    disabled={isDisabled}
                    className={cn(
                      "group flex w-full flex-col items-center gap-2 rounded-2xl border px-3 py-4 text-center transition-all duration-200",
                      isDisabled
                        ? "cursor-not-allowed border-border/50 bg-muted/30 opacity-50"
                        : activeFeature === action.id
                          ? "border-primary/40 bg-primary/5 ring-1 ring-primary/20 hover:bg-primary/10"
                          : "border-border bg-card hover:bg-muted"
                    )}
                  >
                    <span
                      className={cn(
                        "flex size-10 shrink-0 items-center justify-center rounded-xl transition-colors",
                        isDisabled
                          ? "bg-muted text-muted-foreground/60"
                          : activeFeature === action.id
                            ? "bg-primary/20 text-primary"
                            : "bg-muted text-muted-foreground group-hover:text-foreground"
                      )}
                    >
                      <ActionIcon className="size-5" />
                    </span>
                    <span className="flex flex-col gap-0.5">
                      <span className="text-xs leading-tight font-semibold text-foreground">
                        {action.label}
                      </span>
                      <span className="text-[11px] leading-snug text-muted-foreground">
                        {action.description}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Saved outputs — scrollable area with no scrollbar */}
          <div className={cn("border-t min-h-0 flex-1 flex flex-col", !showSavedOutputs && "")}>
            {isReportsLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2Icon className="size-4 animate-spin" />
              </div>
            ) : showSavedOutputs ? (
              <>
                <p className="px-4 pt-3 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                  Saved outputs
                </p>
                <div className="min-h-0 flex-1 overflow-y-auto [&::-webkit-scrollbar]:hidden [& scrollbar-width-none]">
                  <ItemGroup className="px-3 pt-3 pb-3">
                    {isMindMapGenerating && (
                      <Item
                        variant="muted"
                        size="xs"
                        className="cursor-default opacity-70 select-none"
                      >
                        <ItemMedia className="size-7 rounded-md border border-border bg-muted/30 text-muted-foreground">
                          <Loader2Icon className="size-3.5 animate-spin" />
                        </ItemMedia>
                        <ItemContent>
                          <ItemTitle className="text-xs">Mind Map</ItemTitle>
                          <ItemDescription className="animate-pulse text-[11px]">
                            Processing…
                          </ItemDescription>
                        </ItemContent>
                      </Item>
                    )}
                    {reports &&
                      reports.map((r) => (
                        <ReportItem
                          key={r.id}
                          report={r}
                          notebookId={notebookId}
                          onViewReport={onViewReport}
                          isReportInProgress={isReportInProgress}
                          renderReportIcon={renderReportIcon}
                          renderReportDescription={renderReportDescription}
                        />
                      ))}
                  </ItemGroup>
                </div>
              </>
            ) : (
              <Empty className="border-0 px-4 py-8">
                <EmptyHeader className="gap-2.5">
                  <EmptyTitle className="text-sm font-medium">
                    Studio output will be saved here.
                  </EmptyTitle>
                  <EmptyDescription className="max-w-72 text-xs leading-relaxed text-muted-foreground/90">
                    After adding sources, click to add Audio Overview, Study
                    Guide, Mind Map, and more!
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}
          </div>

          {/* Fixed bottom buttons — always visible, never scrolled */}
          <div className="shrink-0 border-t px-4 pt-3 pb-4">
            <Button variant="outline" size="default" className="w-full text-sm">
              <PlusIcon data-icon="inline-start" />
              Add note
            </Button>
            {onToggleCollapse ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onToggleCollapse}
                className="mt-2.5 w-full justify-start text-muted-foreground"
              >
                <PanelRightCloseIcon data-icon="inline-start" />
                Collapse panel
              </Button>
            ) : null}
          </div>
        </>
      )}
    </div>
  )
}

function ReportItem({
  report,
  notebookId,
  onViewReport,
  isReportInProgress,
  renderReportIcon,
  renderReportDescription,
}: {
  report: NotebookReport
  notebookId?: string
  onViewReport?: (report: NotebookReport) => void
  isReportInProgress: (report: NotebookReport) => boolean
  renderReportIcon: (report: NotebookReport) => React.ReactNode
  renderReportDescription: (report: NotebookReport) => React.ReactNode
}) {
  const [isHovered, setIsHovered] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const deleteMutation = useDeleteNotebookReportMutation(
    notebookId ?? "",
    report.id
  )
  const inProgress = isReportInProgress(report)
  const meta = REPORT_TYPE_BY_ID[report.reportType]

  function handleDelete() {
    deleteMutation.mutate(undefined, {
      onSuccess: () => {
        setShowDeleteDialog(false)
      },
    })
  }

  return (
    <>
      <Item
        render={inProgress ? undefined : <button />}
        variant={inProgress ? "muted" : "outline"}
        size="xs"
        onClick={
          inProgress ? undefined : () => onViewReport?.(report)
        }
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={cn(
          inProgress
            ? "cursor-default opacity-70 select-none"
            : "cursor-pointer border-border/40 bg-background hover:border-primary/20 hover:bg-muted/40"
        )}
      >
        <ItemMedia className="size-7 rounded-md border border-border bg-muted/30 text-muted-foreground">
          {renderReportIcon(report)}
        </ItemMedia>
        <ItemContent>
          <ItemTitle className="text-xs">
            {meta?.label ?? report.reportType}
          </ItemTitle>
          <ItemDescription className="text-[11px]">
            {renderReportDescription(report)}
          </ItemDescription>
        </ItemContent>
        {!inProgress && (
          <ItemActions>
            {isHovered && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setShowDeleteDialog(true)
                }}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                aria-label="Delete report"
              >
                <Trash2Icon className="size-3.5" />
              </button>
            )}
          </ItemActions>
        )}
      </Item>

      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete report</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this {meta?.label ?? report.reportType}? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
