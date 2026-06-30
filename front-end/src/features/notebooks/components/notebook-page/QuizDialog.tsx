import { useState } from "react"
import { CheckCircle2Icon, RotateCcwIcon, XCircleIcon } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import type { NotebookReport, QuizContent } from "@/features/notebooks/types"

export function QuizDialog({
  open,
  onOpenChange,
  report,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  report?: NotebookReport | null
}) {
  const questions =
    report && report.reportType === "quiz"
      ? (report.content.questions ?? [])
      : []

  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [submitted, setSubmitted] = useState(false)

  const status = report?.status
  const isCompleted = status === "completed"
  const answeredCount = Object.keys(answers).length
  const allAnswered =
    questions.length > 0 && answeredCount === questions.length
  const score = questions.reduce(
    (acc, q, i) => acc + (answers[i] === q.correct_index ? 1 : 0),
    0
  )

  function getStatusDescription(): string {
    if (isCompleted) {
      return submitted
        ? `You scored ${score} / ${questions.length}`
        : `${questions.length} questions · answer each, then submit`
    }
    if (status === "failed") return "Generation failed"
    if (status === "cancelled") return "Cancelled"
    return "Generating quiz..."
  }

  function renderBody() {
    if (report && isCompleted && questions.length > 0) {
      return (
        <div className="space-y-4 p-5">
          {submitted ? (
            <ScoreBanner score={score} total={questions.length} />
          ) : null}
          <ol className="space-y-4">
            {questions.map((q, i) => (
              <QuizQuestionView
                key={i}
                index={i}
                question={q}
                selected={answers[i]}
                submitted={submitted}
                onSelect={(optionIndex) => {
                  if (submitted) return
                  setAnswers((prev) => ({ ...prev, [i]: optionIndex }))
                }}
              />
            ))}
          </ol>
        </div>
      )
    }
    if (report && isCompleted) {
      return (
        <div className="p-6 text-sm text-muted-foreground">
          This quiz has no questions.
        </div>
      )
    }
    if (status === "failed") {
      return (
        <div className="p-6 text-sm text-destructive">
          {report?.errorMessage ?? "Quiz generation failed."}
        </div>
      )
    }
    if (status === "cancelled") {
      return (
        <div className="p-6 text-sm text-muted-foreground">
          This quiz was cancelled.
        </div>
      )
    }
    return (
      <div className="flex items-center justify-center p-6 text-sm text-muted-foreground">
        Generating quiz...
      </div>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(90vh,42rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="border-b px-5 py-3.5 pr-12">
          <DialogTitle className="truncate text-sm font-semibold text-foreground">
            Quiz
          </DialogTitle>
          <DialogDescription className="truncate text-[11px] text-muted-foreground">
            {getStatusDescription()}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="min-h-0 flex-1">{renderBody()}</ScrollArea>

        {report && isCompleted && questions.length > 0 ? (
          <div className="flex items-center justify-between gap-3 border-t px-5 py-3">
            <span className="text-[11px] text-muted-foreground">
              {submitted
                ? `Score: ${score} / ${questions.length}`
                : `${answeredCount} / ${questions.length} answered`}
            </span>
            {submitted ? (
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => {
                  setAnswers({})
                  setSubmitted(false)
                }}
              >
                <RotateCcwIcon className="size-3.5" />
                Retake
              </Button>
            ) : (
              <Button
                size="sm"
                disabled={!allAnswered}
                onClick={() => setSubmitted(true)}
              >
                Submit
              </Button>
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function ScoreBanner({ score, total }: { score: number; total: number }) {
  const pct = total > 0 ? Math.round((score / total) * 100) : 0
  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 text-center">
      <p className="text-2xl font-bold text-foreground">
        {score} / {total}
      </p>
      <p className="text-xs text-muted-foreground">{pct}% correct</p>
    </div>
  )
}

function QuizQuestionView({
  index,
  question,
  selected,
  submitted,
  onSelect,
}: {
  index: number
  question: QuizContent["questions"][number]
  selected: number | undefined
  submitted: boolean
  onSelect: (optionIndex: number) => void
}) {
  return (
    <li className="space-y-3 rounded-lg border border-border/50 bg-card p-4">
      <p className="text-sm font-medium text-foreground">
        <span className="mr-1.5 text-muted-foreground">{index + 1}.</span>
        {question.question}
      </p>
      <div className="grid grid-cols-1 gap-1.5">
        {question.options.map((opt, i) => {
          const isSelected = selected === i
          const isCorrect = submitted && i === question.correct_index
          const isWrongChoice =
            submitted && isSelected && i !== question.correct_index
          return (
            <button
              key={i}
              type="button"
              onClick={() => onSelect(i)}
              disabled={submitted}
              className={cn(
                "flex items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                !submitted &&
                  "cursor-pointer hover:border-primary/30 hover:bg-muted/40",
                submitted && "cursor-default",
                !submitted && isSelected && "border-primary/60 bg-primary/10",
                isCorrect &&
                  "border-emerald-500/40 bg-emerald-500/10 text-foreground",
                isWrongChoice && "border-red-500/40 bg-red-500/10 text-foreground",
                !isSelected &&
                  !isCorrect &&
                  !isWrongChoice &&
                  "border-border/50"
              )}
            >
              {submitted && isCorrect ? (
                <CheckCircle2Icon className="size-4 shrink-0 text-emerald-500" />
              ) : submitted && isWrongChoice ? (
                <XCircleIcon className="size-4 shrink-0 text-red-500" />
              ) : (
                <span className="flex size-4 shrink-0 items-center justify-center rounded-full border border-current text-[10px] text-muted-foreground">
                  {String.fromCharCode(65 + i)}
                </span>
              )}
              <span>{opt}</span>
            </button>
          )
        })}
      </div>
      {submitted ? (
        <div className="border-l-2 border-primary/40 py-1 pl-3 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Explanation: </span>
          {question.explanation}
        </div>
      ) : null}
    </li>
  )
}
