import {
  BotIcon,
  BrainCircuitIcon,
  CheckCircle2Icon,
  FileQuestionIcon,
  FileTextIcon,
  GitBranchIcon,
  Layers3Icon,
  MessageSquareTextIcon,
  MoreHorizontalIcon,
  PlusIcon,
  SearchIcon,
  SparklesIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"

const sources = [
  { name: "AI Outlook 2026.pdf", chunks: 28 },
  { name: "Research Notes.md", chunks: 12 },
  { name: "Market Brief.docx", chunks: 19 },
]

const studioTools = [
  { label: "Mind Map", icon: GitBranchIcon },
  { label: "Flashcards", icon: Layers3Icon },
  { label: "Quiz", icon: FileQuestionIcon },
  { label: "Reports", icon: FileTextIcon },
]

export function ProductPreview() {
  return (
    <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div className="absolute inset-x-16 -top-10 h-48 rounded-full bg-primary/20 blur-3xl" />
      <div
        data-preview-tilt
        className="group/preview relative overflow-hidden rounded-[28px] border border-white/10 bg-white/5 p-2 shadow-[0_32px_100px_-35px_color-mix(in_oklch,var(--primary)_35%,transparent)] backdrop-blur-xl transition-[transform,border-color,box-shadow] duration-700 landing-preview-tilt hover:border-white/15 hover:shadow-[0_38px_120px_-35px_color-mix(in_oklch,var(--primary)_45%,transparent)] sm:p-3"
      >
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-[#101013]/95 backdrop-blur-2xl">
          <div className="flex h-12 items-center justify-between border-b border-white/10 px-4">
            <div className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full bg-white/15" />
              <span className="size-2.5 rounded-full bg-white/15" />
              <span className="size-2.5 rounded-full bg-white/15" />
            </div>
            <div className="text-[11px] text-white/35">
              AI Research · Notebook workspace
            </div>
            <MoreHorizontalIcon className="size-4 text-white/30" />
          </div>

          <div className="grid min-h-[500px] grid-cols-1 lg:grid-cols-[230px_1fr_250px]">
            <div className="grid grid-cols-3 border-b border-white/10 bg-white/[0.012] lg:hidden">
              <div className="border-r border-white/10 px-3 py-3.5 sm:px-5">
                <div className="flex items-center gap-2 text-indigo-300">
                  <FileTextIcon className="size-3.5 shrink-0" />
                  <span className="text-[11px] font-medium text-white/75">
                    Sources
                  </span>
                </div>
                <p className="mt-1 pl-5.5 text-[9px] text-white/35">
                  3 indexed
                </p>
              </div>
              <div className="border-r border-white/10 bg-primary/[0.06] px-3 py-3.5 sm:px-5">
                <div className="flex items-center gap-2 text-indigo-300">
                  <MessageSquareTextIcon className="size-3.5 shrink-0" />
                  <span className="text-[11px] font-medium text-white/85">
                    Chat
                  </span>
                </div>
                <p className="mt-1 pl-5.5 text-[9px] text-white/35">
                  With citations
                </p>
              </div>
              <div className="px-3 py-3.5 sm:px-5">
                <div className="flex items-center gap-2 text-indigo-300">
                  <SparklesIcon className="size-3.5 shrink-0" />
                  <span className="text-[11px] font-medium text-white/75">
                    Studio
                  </span>
                </div>
                <p className="mt-1 pl-5.5 text-[9px] text-white/35">4 tools</p>
              </div>
            </div>

            <aside className="hidden border-r border-white/10 bg-white/[0.012] p-4 lg:block">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-white/85">Sources</p>
                  <p className="mt-1 text-[10px] text-white/35">
                    3 indexed documents
                  </p>
                </div>
                <span className="flex size-8 items-center justify-center rounded-xl bg-primary/15 text-indigo-300 ring-1 ring-primary/25">
                  <PlusIcon className="size-4" />
                </span>
              </div>
              <div className="relative mb-4">
                <SearchIcon className="absolute top-2.5 left-3 size-3.5 text-white/30" />
                <div className="h-9 rounded-xl border border-white/10 bg-white/[0.03] pl-9 text-xs leading-9 text-white/30">
                  Search sources
                </div>
              </div>
              <div className="space-y-2">
                {sources.map((source) => (
                  <div
                    key={source.name}
                    className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] p-3 transition-[background-color,border-color,transform] duration-300 hover:translate-x-0.5 hover:border-primary/20 hover:bg-white/[0.045]"
                  >
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-indigo-400/10 text-indigo-300">
                      <FileTextIcon className="size-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[11px] text-white/70">
                        {source.name}
                      </p>
                      <p className="mt-0.5 flex items-center gap-1 text-[10px] text-white/30">
                        <CheckCircle2Icon className="size-2.5 animate-pulse text-emerald-300 [animation-duration:2.8s]" />
                        Indexed · {source.chunks} chunks
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-center gap-2 rounded-xl border border-dashed border-white/10 py-3 text-[11px] text-white/35">
                <PlusIcon className="size-3.5" /> Upload source
              </div>
            </aside>

            <main className="flex min-w-0 flex-col bg-gradient-to-b from-white/[0.018] to-transparent p-4 sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs text-white/40">Notebook Assistant</p>
                  <h3 className="mt-1 text-lg font-semibold text-white">
                    The future of agentic AI
                  </h3>
                </div>
                <Badge
                  variant="outline"
                  className="border-primary/20 bg-primary/10 text-indigo-200"
                >
                  <BrainCircuitIcon /> 3 sources
                </Badge>
              </div>

              <Separator className="my-5 bg-white/10" />

              <div className="space-y-5">
                <div className="ml-auto max-w-[88%] rounded-2xl rounded-tr-md bg-white/8 px-4 py-3 text-sm leading-6 text-white/75">
                  What opportunities and risks do these reports identify for
                  agentic AI?
                </div>
                <div className="flex gap-3">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary/20 text-indigo-300 ring-1 ring-primary/30">
                    <BotIcon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1 space-y-3">
                    <p className="text-sm leading-6 text-white/65">
                      Across your notebook, three opportunities stand out:
                      autonomous workflows, personalized knowledge systems, and
                      faster research synthesis. The main risks are reliability,
                      governance, and context quality.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Badge
                        variant="outline"
                        className="border-white/10 text-white/45"
                      >
                        [1] AI Outlook.pdf
                      </Badge>
                      <Badge
                        variant="outline"
                        className="border-white/10 text-white/45"
                      >
                        [2] Research Notes.md
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-auto flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-white/35 shadow-lg shadow-black/10">
                <MessageSquareTextIcon className="size-4" />
                <span className="flex-1 text-xs">
                  Ask anything about this notebook...
                  <span className="ml-0.5 inline-block h-3 w-px landing-cursor" />
                </span>
                <span className="flex size-7 items-center justify-center rounded-lg bg-primary/20 text-indigo-300">
                  <SparklesIcon className="size-3.5" />
                </span>
              </div>
            </main>

            <aside className="hidden border-l border-white/10 bg-white/[0.012] p-4 lg:block">
              <div className="mb-4">
                <p className="text-xs font-semibold text-white/85">Studio</p>
                <p className="mt-1 text-[10px] text-white/35">
                  Create from your knowledge
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {studioTools.map((tool) => {
                  const Icon = tool.icon
                  return (
                    <div
                      key={tool.label}
                      className="group/tool rounded-xl border border-white/8 bg-white/[0.025] p-3 transition-[background-color,border-color,transform] duration-300 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-white/5"
                    >
                      <Icon className="size-4 text-indigo-300 transition-transform duration-300 group-hover/tool:rotate-[4deg]" />
                      <p className="mt-2 text-[10px] text-white/60">
                        {tool.label}
                      </p>
                    </div>
                  )
                })}
              </div>

              <div className="mt-4 rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/15 to-white/[0.025] p-4 shadow-lg shadow-primary/5">
                <div className="flex items-center justify-between">
                  <span className="flex size-8 items-center justify-center rounded-xl bg-primary/20 text-indigo-200">
                    <GitBranchIcon className="size-4" />
                  </span>
                  <Badge
                    variant="outline"
                    className="border-white/10 text-white/40"
                  >
                    Generated
                  </Badge>
                </div>
                <p className="mt-4 text-xs font-medium text-white/80">
                  Agentic AI landscape
                </p>
                <div className="mt-4 space-y-2">
                  {["Autonomous systems", "Knowledge agents", "Governance"].map(
                    (topic, index) => (
                      <div key={topic} className="flex items-center gap-2">
                        <span className="size-1.5 rounded-full bg-indigo-300" />
                        <span className="text-[10px] text-white/45">
                          {topic}
                        </span>
                        {index < 2 ? (
                          <span className="h-px flex-1 bg-white/8" />
                        ) : null}
                      </div>
                    )
                  )}
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </div>
  )
}
