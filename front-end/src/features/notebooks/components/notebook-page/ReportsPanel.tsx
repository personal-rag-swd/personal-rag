import * as React from "react"
import { useState } from "react"
import { CheckCircle2Icon } from "lucide-react"
import { formatDistanceToNow } from "date-fns"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import type {
  BlogPostContent,
  BriefingDocContent,
  CustomReportContent,
  NotebookReport,
  StudyGuideContent,
  NoteContent,
} from "@/features/notebooks/types"

import { REPORT_TYPE_BY_ID } from "./reportTypes"

export function ReportsPanel({
  open,
  onOpenChange,
  report,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  report?: NotebookReport | null
}) {
  const meta = report ? REPORT_TYPE_BY_ID[report.reportType] : null
  const isCompleted = report?.status === "completed"
  const isFailed = report?.status === "failed"
  const isCancelled = report?.status === "cancelled"
  const isPending =
    report?.status === "pending" || report?.status === "generating"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(90vh,38rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="border-b px-5 py-3.5 pr-12">
          <DialogTitle className="truncate text-sm font-semibold text-foreground">
            {meta?.label ?? "Saved report"}
          </DialogTitle>
          <DialogDescription className="truncate text-[11px] text-muted-foreground">
            {report
              ? isPending
                ? "Generating..."
                : isFailed
                  ? "Generation failed"
                  : isCancelled
                    ? "Cancelled"
                    : `Generated ${formatDistanceToNow(new Date(report.createdAt), { addSuffix: true })}`
              : "This saved output could not be loaded."}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="min-h-0 flex-1">
          {report && isCompleted ? (
            <ReportContentView report={report} />
          ) : isFailed ? (
            <div className="p-6 text-sm text-destructive">
              {report.errorMessage ?? "Report generation failed."}
            </div>
          ) : isCancelled ? (
            <div className="p-6 text-sm text-muted-foreground">
              This report was cancelled.
            </div>
          ) : isPending ? (
            <div className="flex items-center justify-center p-6 text-sm text-muted-foreground">
              Generating report...
            </div>
          ) : (
            <div className="p-6 text-sm text-muted-foreground">
              This saved output is unavailable.
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}

function ReportContentView({ report }: { report: NotebookReport }) {
  switch (report.reportType) {
    case "briefing":
      return <BriefingDocView content={report.content} />
    case "study_guide":
      return <StudyGuideView content={report.content} />
    case "blog":
      return <BlogPostView content={report.content} />
    case "custom":
      return <CustomReportView content={report.content} />
    case "note":
      return <NoteReportView content={report.content} />
  }
}

function BriefingDocView({ content }: { content: BriefingDocContent }) {
  return (
    <div className="max-w-3xl space-y-6 p-6">
      <Section title="Executive Summary">
        <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
          {content.executive_summary}
        </p>
      </Section>
      <Section title="Key Takeaways">
        <ul className="space-y-2">
          {content.key_takeaways.map((item, i) => (
            <li
              key={i}
              className="flex gap-2 text-sm leading-relaxed text-foreground"
            >
              <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-500" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Strategic Implications">
        <ul className="space-y-2">
          {content.strategic_implications.map((item, i) => (
            <li
              key={i}
              className="flex gap-2 text-sm leading-relaxed text-foreground"
            >
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-blue-500/10 text-[10px] font-semibold text-blue-500">
                {i + 1}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}

function StudyGuideView({ content }: { content: StudyGuideContent }) {
  return (
    <div className="max-w-3xl space-y-6 p-6">
      <Section title="Glossary">
        <dl className="space-y-3">
          {content.glossary.map((entry, i) => (
            <div
              key={i}
              className="rounded-lg border border-border/50 bg-card p-3"
            >
              <dt className="text-sm font-semibold text-foreground">
                {entry.term}
              </dt>
              <dd className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {entry.definition}
              </dd>
            </div>
          ))}
        </dl>
      </Section>
      <Section title="Quiz">
        <ol className="space-y-4">
          {content.quiz.map((q, i) => (
            <QuizItemView key={i} index={i} item={q} />
          ))}
        </ol>
      </Section>
    </div>
  )
}

function QuizItemView({
  index,
  item,
}: {
  index: number
  item: StudyGuideContent["quiz"][number]
}) {
  const [revealed, setRevealed] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <li className="space-y-3 rounded-lg border border-border/50 bg-card p-4">
      <p className="text-sm font-medium text-foreground">
        <span className="mr-1.5 text-muted-foreground">{index + 1}.</span>
        {item.question}
      </p>
      <div className="grid grid-cols-1 gap-1.5">
        {item.options.map((opt, i) => {
          const isCorrect = revealed && opt === item.answer
          const isWrong = revealed && selected === opt && opt !== item.answer
          return (
            <button
              key={i}
              onClick={() => {
                if (revealed) return
                setSelected(opt)
                setRevealed(true)
              }}
              disabled={revealed}
              className={cn(
                "rounded-md border px-3 py-2 text-left text-sm transition-colors",
                !revealed &&
                  "cursor-pointer hover:border-primary/30 hover:bg-muted/40",
                revealed && "cursor-default",
                isCorrect &&
                  "border-emerald-500/40 bg-emerald-500/10 text-foreground",
                isWrong && "border-red-500/40 bg-red-500/10 text-foreground",
                !isCorrect && !isWrong && "border-border/50"
              )}
            >
              {opt}
            </button>
          )
        })}
      </div>
      {revealed ? (
        <div className="border-l-2 border-primary/40 py-1 pl-3 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Explanation: </span>
          {item.explanation}
        </div>
      ) : null}
    </li>
  )
}

function BlogPostView({ content }: { content: BlogPostContent }) {
  return (
    <div className="max-w-3xl space-y-4 p-6">
      <h1 className="text-2xl leading-tight font-bold text-foreground">
        {content.title}
      </h1>
      <p className="text-base leading-relaxed text-muted-foreground italic">
        {content.hook}
      </p>
      <hr className="border-border/40" />
      <MarkdownText content={content.markdown_body} />
    </div>
  )
}

function CustomReportView({ content }: { content: CustomReportContent }) {
  return (
    <div className="max-w-3xl p-6">
      <MarkdownText content={content.markdown_content} />
    </div>
  )
}

function NoteReportView({ content }: { content: NoteContent }) {
  return (
    <div className="max-w-3xl space-y-4 p-6">
      <h1 className="text-2xl leading-tight font-bold text-foreground">
        {content.title}
      </h1>
      <hr className="border-border/40" />
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground">
        {content.content}
      </p>
    </div>
  )
}

function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-2.5">
      <h2 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
        {title}
      </h2>
      {children}
    </section>
  )
}

function MarkdownText({ content }: { content: string }) {
  const lines = content.split("\n")
  const blocks: React.ReactNode[] = []
  let listBuffer: string[] = []
  let listType: "ul" | "ol" | null = null
  let paragraphBuffer: string[] = []

  const flushList = () => {
    if (listBuffer.length === 0) return
    const Tag = listType === "ol" ? "ol" : "ul"
    blocks.push(
      <Tag
        key={`list-${blocks.length}`}
        className={cn(
          "my-3 ml-5 space-y-1 text-sm text-foreground",
          Tag === "ol" ? "list-decimal" : "list-disc"
        )}
      >
        {listBuffer.map((item, i) => (
          <li key={i}>{renderInline(item)}</li>
        ))}
      </Tag>
    )
    listBuffer = []
    listType = null
  }

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) return
    blocks.push(
      <p
        key={`p-${blocks.length}`}
        className="my-3 text-sm leading-relaxed text-foreground"
      >
        {renderInline(paragraphBuffer.join(" "))}
      </p>
    )
    paragraphBuffer = []
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      flushList()
      flushParagraph()
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      flushList()
      flushParagraph()
      const level = heading[1].length
      const text = heading[2]
      const sizes = [
        "text-2xl",
        "text-xl",
        "text-lg",
        "text-base",
        "text-sm",
        "text-sm",
      ]
      blocks.push(
        <div
          key={`h-${blocks.length}`}
          className={cn(
            "mt-5 mb-2 font-semibold text-foreground",
            sizes[level - 1]
          )}
        >
          {renderInline(text)}
        </div>
      )
      continue
    }

    const ulMatch = /^[-*]\s+(.*)$/.exec(line)
    if (ulMatch) {
      flushParagraph()
      if (listType !== "ul") flushList()
      listType = "ul"
      listBuffer.push(ulMatch[1])
      continue
    }

    const olMatch = /^\d+\.\s+(.*)$/.exec(line)
    if (olMatch) {
      flushParagraph()
      if (listType !== "ol") flushList()
      listType = "ol"
      listBuffer.push(olMatch[1])
      continue
    }

    flushList()
    paragraphBuffer.push(line)
  }

  flushList()
  flushParagraph()

  return <div>{blocks}</div>
}

function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let lastIndex = 0

  for (const match of text.matchAll(regex)) {
    const full = match[0]
    const index = match.index ?? 0

    if (index > lastIndex) {
      parts.push(text.slice(lastIndex, index))
    }

    if (full.startsWith("**")) {
      parts.push(<strong key={index}>{full.slice(2, -2)}</strong>)
    } else if (full.startsWith("*")) {
      parts.push(<em key={index}>{full.slice(1, -1)}</em>)
    } else if (full.startsWith("`")) {
      parts.push(
        <code
          key={index}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.92em]"
        >
          {full.slice(1, -1)}
        </code>
      )
    }

    lastIndex = index + full.length
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return parts
}
