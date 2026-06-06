import * as React from "react";
import { useEffect, useState } from "react";
import {
  ArrowLeftIcon,
  CheckCircle2Icon,
  ChevronRightIcon,
  FileTextIcon,
  Loader2Icon,
  PlusIcon,
  SparklesIcon,
  XIcon,
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils";

import {
  useGenerateNotebookReportMutation,
  useNotebookReportsQuery,
} from "@/features/notebooks/api";
import type {
  BlogPostContent,
  BriefingDocContent,
  CustomReportContent,
  NotebookReport,
  ReportType,
  StudyGuideContent,
} from "@/features/notebooks/types";
import { REPORT_TYPES, REPORT_TYPE_BY_ID } from "./reportTypes";

export function ReportsPanel({
  notebookId,
  open,
  onOpenChange,
  initialReport,
}: {
  notebookId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialReport?: NotebookReport | null;
}) {
  const [selectedType, setSelectedType] = useState<ReportType>("custom");
  const [instructions, setInstructions] = useState("");
  const [viewingReport, setViewingReport] = useState<NotebookReport | null>(null);

  const { data: reports, isLoading: isReportsLoading } =
    useNotebookReportsQuery(notebookId);
  const generateMutation = useGenerateNotebookReportMutation(notebookId);

  const textReports = reports ? reports.filter((r) => r.reportType !== "mindmap") : [];

  // When opened with a pre-selected report (from StudioPanel), show it directly.
  useEffect(() => {
    if (open && initialReport) {
      setViewingReport(initialReport);
    }
  }, [open, initialReport]);

  // Reset state every time the dialog is closed.
  useEffect(() => {
    if (!open) {
      setSelectedType("custom");
      setInstructions("");
      setViewingReport(null);
    }
  }, [open]);

  const activeMeta = REPORT_TYPE_BY_ID[selectedType];
  const isCustom = selectedType === "custom";
  const canGenerate = !isCustom || instructions.trim().length > 0;

  const handleGenerate = () => {
    if (isCustom && !instructions.trim()) {
      toast.error("Please describe what report you want.");
      return;
    }

    generateMutation.mutate(
      {
        reportType: selectedType,
        additionalInstructions: instructions.trim() || undefined,
      },
      {
        onSuccess: (report) => {
          toast.success("Report generated", {
            description: REPORT_TYPE_BY_ID[selectedType].label,
          });
          setViewingReport(report);
        },
        onError: (error) => {
          toast.error("Failed to generate report", {
            description: error.message,
          });
        },
      }
    );
  };

  const handleCreateAnother = () => {
    setViewingReport(null);
    setInstructions("");
  };

  // Decide which view to show inside the dialog body.
  let body: React.ReactNode;
  let headerTitle = "Reports";
  let headerSubtitle: string | undefined =
    "Generate a structured report from your notebook sources.";
  let headerBack: (() => void) | undefined;

  if (viewingReport) {
    const meta = REPORT_TYPE_BY_ID[viewingReport.reportType];
    headerTitle = meta?.label ?? viewingReport.reportType;
    headerSubtitle = `Generated ${formatDistanceToNow(new Date(viewingReport.createdAt), { addSuffix: true })}`;
    headerBack = () => setViewingReport(null);
    body = (
      <>
        <ScrollArea className="flex-1 min-h-0">
          <ReportContentView report={viewingReport} />
        </ScrollArea>
        <div className="border-t border-border/40 px-4 py-3 shrink-0">
          <Button
            variant="outline"
            onClick={handleCreateAnother}
            className="w-full gap-2"
          >
            <PlusIcon className="size-4" />
            Create another report
          </Button>
        </div>
      </>
    );
  } else {
    body = (
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-6 space-y-6">
          {/* Format selector */}
          <section className="space-y-2.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Format
            </label>
            <ToggleGroup
              value={[selectedType]}
              onValueChange={(value: string[]) => {
                if (value[0]) {
                  setSelectedType(value[0] as ReportType);
                }
              }}
              variant="outline"
              spacing={2}
              className="flex-wrap"
            >
              {REPORT_TYPES.map((t) => (
                <ToggleGroupItem
                  key={t.id}
                  value={t.id}
                  className={cn(
                    "h-9 gap-1.5 rounded-full px-3.5 text-xs font-medium",
                    "data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
                  )}
                >
                  <span
                    className={cn(
                      "shrink-0 transition-colors",
                      selectedType === t.id
                        ? "text-primary-foreground"
                        : "text-muted-foreground"
                    )}
                  >
                    {t.icon}
                  </span>
                  {t.shortLabel}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
            <p className="text-xs text-muted-foreground">{activeMeta.description}</p>
          </section>

          {/* Instructions textarea */}
          <section className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {isCustom ? "Your instructions" : "Additional instructions"}
            </label>
            <Textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder={activeMeta.placeholder}
              rows={6}
              className="resize-none text-sm"
            />
          </section>

          {/* Generate button */}
          <Button
            onClick={handleGenerate}
            disabled={!canGenerate || generateMutation.isPending}
            className="w-full gap-2"
            size="lg"
          >
            {generateMutation.isPending ? (
              <>
                <Loader2Icon className="size-4 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <SparklesIcon className="size-4" />
                Generate
              </>
            )}
          </Button>

          {/* Recent reports */}
          {(isReportsLoading || textReports.length > 0) && (
            <section className="pt-2">
              <h3 className="px-1 mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Recent reports
              </h3>
              {isReportsLoading ? (
                <div className="flex items-center justify-center py-6 text-muted-foreground">
                  <Loader2Icon className="size-4 animate-spin" />
                </div>
              ) : (
                <div className="space-y-1.5">
                  {textReports.map((r) => {
                    const meta = REPORT_TYPE_BY_ID[r.reportType];
                    return (
                      <button
                        key={r.id}
                        onClick={() => setViewingReport(r)}
                        className="group flex w-full items-center gap-2.5 p-2.5 rounded-lg border border-border/40 bg-card hover:bg-muted/40 hover:border-primary/20 transition-all text-left cursor-pointer"
                      >
                        <div
                          className={cn(
                            "flex size-7 shrink-0 items-center justify-center rounded-md border",
                            meta?.colorClass ?? "text-muted-foreground bg-muted/30 border-border"
                          )}
                        >
                          {meta?.icon ?? <FileTextIcon className="size-3.5" />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-foreground truncate">
                            {meta?.label ?? r.reportType}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {formatDistanceToNow(new Date(r.createdAt), {
                              addSuffix: true,
                            })}
                          </p>
                        </div>
                        <ChevronRightIcon className="size-3.5 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          )}
        </div>
      </ScrollArea>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="flex flex-col p-0 gap-0 max-w-[min(100%-2rem,56rem)] sm:max-w-[min(100%-2rem,56rem)] h-[min(100%-4rem,42rem)] overflow-hidden"
      >
        <PanelHeader
          title={headerTitle}
          subtitle={headerSubtitle}
          onBack={headerBack}
          onClose={() => onOpenChange(false)}
        />
        {body}
      </DialogContent>
    </Dialog>
  );
}

// ─── Sub-components ────────────────────────────────────────────────────────

function PanelHeader({
  title,
  subtitle,
  onBack,
  onClose,
}: {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  onClose: () => void;
}) {
  return (
    <div className="flex items-center gap-2 px-4 py-3 border-b border-border/40 shrink-0">
      {onBack && (
        <button
          onClick={onBack}
          className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
          aria-label="Back"
        >
          <ArrowLeftIcon className="size-4" />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <DialogTitle className="text-sm font-semibold text-foreground truncate">
          {title}
        </DialogTitle>
        {subtitle && (
          <DialogDescription className="text-[11px] text-muted-foreground truncate">
            {subtitle}
          </DialogDescription>
        )}
      </div>
      <button
        onClick={onClose}
        className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
        aria-label="Close reports"
      >
        <XIcon className="size-4" />
      </button>
    </div>
  );
}

function ReportContentView({ report }: { report: NotebookReport }) {
  switch (report.reportType) {
    case "briefing":
      return <BriefingDocView content={report.content as BriefingDocContent} />;
    case "study_guide":
      return <StudyGuideView content={report.content as StudyGuideContent} />;
    case "blog":
      return <BlogPostView content={report.content as BlogPostContent} />;
    case "custom":
      return <CustomReportView content={report.content as CustomReportContent} />;
    default:
      return null;
  }
}

function BriefingDocView({ content }: { content: BriefingDocContent }) {
  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <Section title="Executive Summary">
        <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">
          {content.executive_summary}
        </p>
      </Section>
      <Section title="Key Takeaways">
        <ul className="space-y-2">
          {content.key_takeaways.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-foreground leading-relaxed">
              <CheckCircle2Icon className="size-4 shrink-0 mt-0.5 text-emerald-500" />
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
              className="flex gap-2 text-sm text-foreground leading-relaxed"
            >
              <span className="shrink-0 mt-0.5 flex size-5 items-center justify-center rounded-full bg-blue-500/10 text-blue-500 text-[10px] font-semibold">
                {i + 1}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

function StudyGuideView({ content }: { content: StudyGuideContent }) {
  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <Section title="Glossary">
        <dl className="space-y-3">
          {content.glossary.map((entry, i) => (
            <div key={i} className="rounded-lg border border-border/50 bg-card p-3">
              <dt className="text-sm font-semibold text-foreground">{entry.term}</dt>
              <dd className="mt-1 text-sm text-muted-foreground leading-relaxed">
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
  );
}

function QuizItemView({
  index,
  item,
}: {
  index: number;
  item: StudyGuideContent["quiz"][number];
}) {
  const [revealed, setRevealed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <li className="rounded-lg border border-border/50 bg-card p-4 space-y-3">
      <p className="text-sm font-medium text-foreground">
        <span className="text-muted-foreground mr-1.5">{index + 1}.</span>
        {item.question}
      </p>
      <div className="grid grid-cols-1 gap-1.5">
        {item.options.map((opt, i) => {
          const isCorrect = revealed && opt === item.answer;
          const isWrong = revealed && selected === opt && opt !== item.answer;
          return (
            <button
              key={i}
              onClick={() => {
                if (revealed) return;
                setSelected(opt);
                setRevealed(true);
              }}
              disabled={revealed}
              className={cn(
                "text-left text-sm rounded-md border px-3 py-2 transition-colors",
                !revealed && "cursor-pointer hover:bg-muted/40 hover:border-primary/30",
                revealed && "cursor-default",
                isCorrect && "border-emerald-500/40 bg-emerald-500/10 text-foreground",
                isWrong && "border-red-500/40 bg-red-500/10 text-foreground",
                !isCorrect && !isWrong && "border-border/50"
              )}
            >
              {opt}
            </button>
          );
        })}
      </div>
      {revealed && (
        <div className="text-xs text-muted-foreground border-l-2 border-primary/40 pl-3 py-1">
          <span className="font-semibold text-foreground">Explanation: </span>
          {item.explanation}
        </div>
      )}
    </li>
  );
}

function BlogPostView({ content }: { content: BlogPostContent }) {
  return (
    <div className="p-6 max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold text-foreground leading-tight">
        {content.title}
      </h1>
      <p className="text-base text-muted-foreground italic leading-relaxed">
        {content.hook}
      </p>
      <hr className="border-border/40" />
      <MarkdownText content={content.markdown_body} />
    </div>
  );
}

function CustomReportView({ content }: { content: CustomReportContent }) {
  return (
    <div className="p-6 max-w-3xl">
      <MarkdownText content={content.markdown_content} />
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2.5">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  );
}

// Minimal markdown renderer: preserves headings, lists, paragraphs, bold/italic, inline code.
// Good enough for blog/custom output without pulling in a full markdown library.
function MarkdownText({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let paragraphBuffer: string[] = [];

  const flushList = () => {
    if (listBuffer.length === 0) return;
    const Tag = listType === "ol" ? "ol" : "ul";
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
    );
    listBuffer = [];
    listType = null;
  };

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) return;
    blocks.push(
      <p
        key={`p-${blocks.length}`}
        className="my-3 text-sm leading-relaxed text-foreground"
      >
        {renderInline(paragraphBuffer.join(" "))}
      </p>
    );
    paragraphBuffer = [];
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flushList();
      flushParagraph();
      continue;
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      flushList();
      flushParagraph();
      const level = heading[1].length;
      const text = heading[2];
      const sizes = ["text-2xl", "text-xl", "text-lg", "text-base", "text-sm", "text-sm"];
      blocks.push(
        <div
          key={`h-${blocks.length}`}
          className={cn(
            "font-semibold text-foreground mt-5 mb-2",
            sizes[level - 1]
          )}
        >
          {renderInline(text)}
        </div>
      );
      continue;
    }

    const ulMatch = /^[-*]\s+(.*)$/.exec(line);
    if (ulMatch) {
      flushParagraph();
      if (listType !== "ul") flushList();
      listType = "ul";
      listBuffer.push(ulMatch[1]);
      continue;
    }

    const olMatch = /^\d+\.\s+(.*)$/.exec(line);
    if (olMatch) {
      flushParagraph();
      if (listType !== "ol") flushList();
      listType = "ol";
      listBuffer.push(olMatch[1]);
      continue;
    }

    flushList();
    paragraphBuffer.push(line);
  }

  flushList();
  flushParagraph();

  return <div>{blocks}</div>;
}

function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  // Split on **bold**, *italic*, and `code`
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(
        <strong key={i++} className="font-semibold text-foreground">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("*")) {
      parts.push(
        <em key={i++} className="italic">
          {token.slice(1, -1)}
        </em>
      );
    } else if (token.startsWith("`")) {
      parts.push(
        <code
          key={i++}
          className="rounded bg-muted/60 px-1 py-0.5 text-[0.85em] font-mono"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}
