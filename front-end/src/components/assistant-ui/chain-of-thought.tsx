import { useEffect, useState, type ElementType, type ReactNode } from "react"
import { BrainIcon, ChevronDownIcon } from "lucide-react"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface ChainOfThoughtProps extends React.PropsWithChildren {
  isRunning: boolean
  className?: string
}

/**
 * Collapsible container that renders an agent's reasoning and tool calls as a
 * flat sequence of steps (see {@link ChainOfThoughtStep}). Styled entirely with
 * shadcn tokens.
 */
export function ChainOfThought({
  isRunning,
  children,
  className,
}: ChainOfThoughtProps) {
  const [isOpen, setIsOpen] = useState(isRunning)

  useEffect(() => {
    if (isRunning) setIsOpen(true)
  }, [isRunning])

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn(
        "my-3 w-full overflow-hidden rounded-xl border border-border bg-muted/20 transition-colors duration-300 dark:bg-muted/5",
        isRunning && "border-primary/30 shadow-xs",
        className
      )}
    >
      <CollapsibleTrigger
        className={cn(
          "flex w-full cursor-pointer items-center justify-between px-4 py-3 text-start transition-colors hover:bg-muted/30 focus-visible:outline-hidden",
          isOpen && "border-b border-border/50"
        )}
      >
        <div className="flex items-center gap-2.5">
          <BrainIcon
            className={cn(
              "size-4 transition-colors",
              isRunning
                ? "animate-pulse text-primary"
                : "text-muted-foreground/80"
            )}
          />
          <span
            className={cn(
              "text-sm font-medium transition-colors",
              isRunning
                ? "animate-pulse text-primary"
                : "text-muted-foreground"
            )}
          >
            Chain of Thought
          </span>
        </div>
        <ChevronDownIcon
          className={cn(
            "size-4 shrink-0 text-muted-foreground/75 transition-transform duration-200 ease-in-out",
            isOpen ? "rotate-0" : "-rotate-90"
          )}
        />
      </CollapsibleTrigger>

      <CollapsibleContent className="ease-out data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
        <div className="space-y-1 px-4 py-3">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  )
}

interface ChainOfThoughtStepProps extends React.PropsWithChildren {
  icon: ElementType
  label: ReactNode
  /** Drives the shimmer/pulse treatment while the step is still in progress. */
  active?: boolean
  className?: string
}

/**
 * One step in the chain: a leading icon sitting on a short connector line, a
 * label, and optional content (search results, reasoning text) beneath it.
 */
export function ChainOfThoughtStep({
  icon: Icon,
  label,
  active = false,
  children,
  className,
}: ChainOfThoughtStepProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-[1rem_1fr] gap-x-3 animate-in fade-in slide-in-from-bottom-1 duration-200",
        className
      )}
    >
      <div className="flex justify-center pt-0.5">
        <Icon
          className={cn(
            "size-4 shrink-0",
            active
              ? "animate-pulse text-foreground"
              : "text-muted-foreground"
          )}
        />
      </div>
      <div
        className={cn(
          "min-w-0 self-center text-sm leading-5",
          active ? "text-foreground" : "text-muted-foreground"
        )}
      >
        {label}
      </div>

      {children != null && (
        <div className="col-start-2 min-w-0 pt-1 pb-2 text-sm text-muted-foreground/90">
          {children}
        </div>
      )}
    </div>
  )
}

/** Row of source chips shown under a search step. */
export function ChainOfThoughtSearchResults({
  children,
  className,
}: React.PropsWithChildren<{ className?: string }>) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {children}
    </div>
  )
}

interface ChainOfThoughtSearchResultProps extends React.PropsWithChildren {
  icon?: ElementType
  className?: string
}

/** A single source chip (e.g. a notebook filename) within a search step. */
export function ChainOfThoughtSearchResult({
  icon: Icon,
  children,
  className,
}: ChainOfThoughtSearchResultProps) {
  return (
    <Badge
      variant="secondary"
      className={cn("max-w-full gap-1 font-normal", className)}
    >
      {Icon && <Icon className="shrink-0 text-muted-foreground" />}
      <span className="truncate">{children}</span>
    </Badge>
  )
}
