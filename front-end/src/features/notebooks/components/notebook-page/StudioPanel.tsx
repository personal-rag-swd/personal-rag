import { PanelRightCloseIcon, PanelRightOpenIcon, PlusIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
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
      "flex h-full min-h-0 flex-col bg-card transition-all duration-300",
      isCollapsed
        ? "w-14 shrink-0 items-center justify-between py-2"
        : ""
    )}>
      {isCollapsed ? (
        <>
          <div className="flex flex-col items-center gap-3 w-full">
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

            <ScrollArea className="w-full flex-1 max-h-[calc(100vh-140px)]">
              <div className="flex flex-col items-center gap-2.5 px-2">
                {STUDIO_ACTIONS.map((action) => (
                  <StudioActionTooltip key={action.id} action={action} />
                ))}
              </div>
            </ScrollArea>
          </div>

          <div className="flex flex-col items-center w-full px-2">
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
          <ScrollArea className="flex-1 w-full">
            <div className="p-3">
              <div className="grid grid-cols-2 gap-2">
                {STUDIO_ACTIONS.map((action) => {
                  const ActionIcon = action.icon;

                  return (
                    <button
                      key={action.id}
                      className="group flex w-full items-center gap-2.5 rounded-2xl border bg-background p-3 text-left transition-all duration-200 hover:bg-muted"
                    >
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground transition-colors group-hover:text-foreground">
                        <ActionIcon className="size-4" />
                      </span>
                      <span className="flex min-w-0 flex-col gap-1">
                        <span className="line-clamp-1 text-xs font-medium leading-tight text-foreground">
                          {action.label}
                        </span>
                        <span className="line-clamp-2 text-[11px] leading-snug text-muted-foreground">
                          {action.description}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </ScrollArea>

          <div className="w-full border-t p-4 sm:p-5">
            <Empty className="border-0 py-8 px-4">
              <EmptyHeader className="gap-2.5">
                <EmptyTitle className="text-sm font-medium">
                  Studio output will be saved here.
                </EmptyTitle>
                <EmptyDescription className="max-w-72 text-xs text-muted-foreground/90 leading-relaxed">
                  After adding sources, click to add Audio Overview, Study Guide, Mind Map, and more!
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
            <Button
              variant="outline"
              size="default"
              className="mt-4 w-full text-sm"
            >
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
  );
}

function StudioActionTooltip({
  action,
}: {
  action: (typeof STUDIO_ACTIONS)[number];
}) {
  const ActionIcon = action.icon;

  return (
    <Tooltip>
      <TooltipTrigger
        className="flex size-8 shrink-0 items-center justify-center rounded-lg border bg-muted text-xs font-medium text-muted-foreground transition-all duration-200 hover:scale-105 hover:text-foreground"
        aria-label={action.label}
      >
        <ActionIcon className="size-4" />
      </TooltipTrigger>
      <TooltipContent side="left">{action.label}</TooltipContent>
    </Tooltip>
  );
}
