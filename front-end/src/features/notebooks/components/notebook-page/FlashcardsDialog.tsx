import { useState } from "react"
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  RotateCwIcon,
} from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { NotebookReport } from "@/features/notebooks/types"

export function FlashcardsDialog({
  open,
  onOpenChange,
  report,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  report?: NotebookReport | null
}) {
  const cards =
    report && report.reportType === "flashcards"
      ? (report.content.cards ?? [])
      : []

  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  const status = report?.status
  const isCompleted = status === "completed"
  const total = cards.length
  const card = cards[index]

  const goTo = (next: number) => {
    setIndex(next)
    setFlipped(false)
  }

  function getStatusDescription(): string {
    if (isCompleted) {
      return total > 0
        ? `Card ${index + 1} of ${total} · click the card to flip`
        : "No cards"
    }
    if (status === "failed") return "Generation failed"
    if (status === "cancelled") return "Cancelled"
    return "Generating flashcards..."
  }

  function renderBody() {
    if (report && isCompleted && total > 0 && card) {
      return (
        <>
          <button
            type="button"
            onClick={() => setFlipped((prev) => !prev)}
            className="flex min-h-52 w-full max-w-xl flex-col items-center justify-center gap-3 rounded-2xl border bg-card p-8 text-center shadow-sm transition-colors hover:border-primary/30"
          >
            <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
              {flipped ? "Back" : "Front"}
            </span>
            <span
              className={cn(
                "text-foreground",
                flipped ? "text-base leading-relaxed" : "text-xl font-semibold"
              )}
            >
              {flipped ? card.back : card.front}
            </span>
            <span className="mt-2 inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <RotateCwIcon className="size-3" />
              Click to flip
            </span>
          </button>

          <div className="flex w-full max-w-xl items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              disabled={index === 0}
              onClick={() => goTo(index - 1)}
            >
              <ChevronLeftIcon className="size-4" />
              Prev
            </Button>
            <span className="text-xs tabular-nums text-muted-foreground">
              {index + 1} / {total}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              disabled={index >= total - 1}
              onClick={() => goTo(index + 1)}
            >
              Next
              <ChevronRightIcon className="size-4" />
            </Button>
          </div>
        </>
      )
    }
    if (report && isCompleted) {
      return (
        <p className="text-sm text-muted-foreground">This set has no cards.</p>
      )
    }
    if (status === "failed") {
      return (
        <p className="text-sm text-destructive">
          {report?.errorMessage ?? "Flashcard generation failed."}
        </p>
      )
    }
    if (status === "cancelled") {
      return (
        <p className="text-sm text-muted-foreground">This set was cancelled.</p>
      )
    }
    return (
      <p className="text-sm text-muted-foreground">Generating flashcards...</p>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(90vh,34rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl">
        <DialogHeader className="border-b px-5 py-3.5 pr-12">
          <DialogTitle className="truncate text-sm font-semibold text-foreground">
            Flashcards
          </DialogTitle>
          <DialogDescription className="truncate text-[11px] text-muted-foreground">
            {getStatusDescription()}
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-5 p-6">
          {renderBody()}
        </div>
      </DialogContent>
    </Dialog>
  )
}
