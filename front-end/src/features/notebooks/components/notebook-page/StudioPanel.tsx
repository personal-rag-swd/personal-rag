import { ChevronRightIcon, PanelRightCloseIcon, PanelRightOpenIcon, PlusIcon, SparklesIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { STUDIO_ACTIONS } from "./studioActions";

export function StudioPanel({
  isCollapsed,
  onToggleCollapse,
}: {
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  return (
    <div className={cn(
      "flex flex-col h-full bg-background transition-all duration-300",
      isCollapsed
        ? "w-14 items-center justify-between py-3 shrink-0 border-l border-border/50"
        : "lg:border-l border-border/50"
    )}>
      {isCollapsed ? (
        <>
          <div className="flex flex-col items-center gap-4 w-full">
            <Tooltip>
              <TooltipTrigger
                onClick={onToggleCollapse}
                className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground cursor-pointer"
                aria-label="Expand panel"
              >
                <PanelRightOpenIcon className="size-4.5" />
              </TooltipTrigger>
              <TooltipContent side="left">Expand panel</TooltipContent>
            </Tooltip>

            <ScrollArea className="w-full flex-1 max-h-[calc(100vh-140px)]">
              <div className="flex flex-col items-center gap-2.5 px-2">
                {STUDIO_ACTIONS.map((action) => (
                  <Tooltip key={action.id}>
                    <TooltipTrigger
                      className={cn(
                        "flex size-8 shrink-0 items-center justify-center rounded-lg border transition-all duration-200 hover:scale-105 cursor-pointer",
                        action.colorClass
                      )}
                      aria-label={action.label}
                    >
                      {action.icon}
                    </TooltipTrigger>
                    <TooltipContent side="left">{action.label}</TooltipContent>
                  </Tooltip>
                ))}
              </div>
            </ScrollArea>
          </div>

          <div className="flex flex-col items-center w-full px-2">
            <Tooltip>
              <TooltipTrigger
                className="flex size-9 items-center justify-center rounded-full bg-foreground text-background shadow-md hover:bg-foreground/90 transition-colors cursor-pointer"
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
          <div className="flex items-center justify-between px-4 py-3 border-b border-border/40 w-full">
            <span className="text-sm font-semibold text-foreground">Studio</span>
            <Tooltip>
              <TooltipTrigger
                onClick={onToggleCollapse}
                className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
                aria-label="Collapse panel"
              >
                <PanelRightCloseIcon className="size-4" />
              </TooltipTrigger>
              <TooltipContent side="bottom">Collapse panel</TooltipContent>
            </Tooltip>
          </div>

          <ScrollArea className="flex-1 w-full">
            <div className="p-4">
              <div className="grid grid-cols-2 gap-2">
                {STUDIO_ACTIONS.map((action) => (
                  <button
                    key={action.id}
                    className="group flex w-full items-center gap-2.5 p-3 rounded-xl border border-border/50 bg-card hover:bg-muted/40 hover:border-primary/20 transition-all duration-200 text-left cursor-pointer"
                  >
                    <div
                      className={cn(
                        "flex size-8 shrink-0 items-center justify-center rounded-lg border",
                        action.colorClass
                      )}
                    >
                      {action.icon}
                    </div>
                    <span className="min-w-0 flex-1 text-xs font-medium leading-tight text-foreground whitespace-normal wrap-break-word line-clamp-2">
                      {action.label}
                    </span>
                    <ChevronRightIcon className="size-3 shrink-0 self-center text-muted-foreground mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                ))}
              </div>
            </div>
          </ScrollArea>

          <div className="px-4 pb-4 pt-2 border-t border-border/40 w-full">
            <div className="flex flex-col items-center text-center gap-2 py-4">
              <div className="flex size-8 items-center justify-center rounded-xl bg-muted/50 text-muted-foreground">
                <SparklesIcon className="size-4" />
              </div>
              <p className="text-xs font-medium text-foreground">
                Studio output will be saved here.
              </p>
              <p className="text-[11px] text-muted-foreground leading-relaxed max-w-45">
                After adding sources, click to add Audio Overview, Study Guide, Mind Map, and more!
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full rounded-xl gap-1.5 text-xs border-border/60 hover:bg-primary/5 hover:border-primary/30 mt-1"
            >
              <PlusIcon className="size-3.5" />
              Add note
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
