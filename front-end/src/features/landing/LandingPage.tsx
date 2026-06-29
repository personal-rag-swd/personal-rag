import {
  ArrowRightIcon,
  BookOpenIcon,
  BrainCircuitIcon,
  BriefcaseBusinessIcon,
  CheckIcon,
  FileStackIcon,
  FileTextIcon,
  GitForkIcon,
  GraduationCapIcon,
  Layers3Icon,
  LightbulbIcon,
  MessageSquareTextIcon,
  NetworkIcon,
  QuoteIcon,
  SearchCheckIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UploadCloudIcon,
  WandSparklesIcon,
  ZapIcon,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { LandingNavbar } from "@/features/landing/components/landing-navbar"
import { LandingEffects } from "@/features/landing/components/landing-effects"
import { ProductPreview } from "@/features/landing/components/product-preview"
import { AnimatedUpload } from "@/features/landing/components/animated-upload"
import { AnimatedKnowledgeGraph } from "@/features/landing/components/animated-knowledge-graph"
import { AnimatedAsk } from "@/features/landing/components/animated-ask"
import { AnimatedChat } from "@/features/landing/components/animated-chat"
import { AnimatedMindMap } from "@/features/landing/components/animated-mind-map"
import { AnimatedFlashcards } from "@/features/landing/components/animated-flashcards"
import { AnimatedQuiz } from "@/features/landing/components/animated-quiz"
import { AnimatedReport } from "@/features/landing/components/animated-report"
import { AnimatedStudyGuide } from "@/features/landing/components/animated-study-guide"
import { AnimatedBlogDraft } from "@/features/landing/components/animated-blog-draft"
import {
  AnimatedNotebook,
  AnimatedPrivacy,
  AnimatedProcessing,
  AnimatedSearch,
  AnimatedStudio,
} from "@/features/landing/components/feature-illustrations"

const workflow = [
  {
    step: "01",
    title: "Upload",
    description: "Add PDFs, DOCX, Markdown, TXT and notes.",
    icon: UploadCloudIcon,
  },
  {
    step: "02",
    title: "Index",
    description:
      "Automatically chunk, index and prepare documents for semantic search.",
    icon: SearchCheckIcon,
  },
  {
    step: "03",
    title: "Ask",
    description: "Receive grounded AI answers with document citations.",
    icon: MessageSquareTextIcon,
  },
]

const features = [
  {
    title: "Notebook-based Knowledge",
    description: "Organize projects into dedicated workspaces.",
    icon: BookOpenIcon,
    illustration: AnimatedNotebook,
  },
  {
    title: "AI Chat with Sources",
    description: "Every answer references your own documents.",
    icon: QuoteIcon,
    illustration: AnimatedChat,
  },
  {
    title: "Smart Document Processing",
    description: "Automatic indexing and semantic search.",
    icon: FileStackIcon,
    illustration: AnimatedProcessing,
  },
  {
    title: "AI Studio",
    description:
      "Generate quizzes, flashcards, study guides, reports and mind maps.",
    icon: WandSparklesIcon,
    illustration: AnimatedStudio,
  },
  {
    title: "Fast Search",
    description: "Instant semantic retrieval across every indexed source.",
    icon: ZapIcon,
    illustration: AnimatedSearch,
  },
  {
    title: "Privacy First",
    description: "Your knowledge stays inside your workspace.",
    icon: ShieldCheckIcon,
    illustration: AnimatedPrivacy,
  },
]

const reports = [
  { title: "Study Guide", icon: GraduationCapIcon, color: "text-sky-300" },
  { title: "Flashcards", icon: Layers3Icon, color: "text-violet-300" },
  { title: "Quiz", icon: BrainCircuitIcon, color: "text-amber-300" },
  { title: "Mind Map", icon: NetworkIcon, color: "text-emerald-300" },
  { title: "Briefing", icon: BriefcaseBusinessIcon, color: "text-rose-300" },
  { title: "Blog Draft", icon: FileTextIcon, color: "text-indigo-300" },
]

export function LandingPage() {
  return (
    <div className="dark min-h-dvh overflow-x-clip bg-background text-foreground">
      <LandingEffects />
      <LandingNavbar />

      <main>
        <section
          data-hero-motion
          className="relative isolate flex min-h-[calc(100dvh-4rem)] items-center overflow-hidden px-4 py-24 sm:px-6 sm:py-32 lg:px-8 lg:py-36"
        >
          <div
            data-hero-parallax
            className="pointer-events-none absolute inset-[-8px] -z-20 landing-hero-parallax"
          >
            <div className="absolute inset-0 landing-grid-motion landing-grid" />
            <div className="absolute inset-x-0 top-[-18rem] mx-auto h-[40rem] max-w-5xl landing-aurora opacity-80" />
            <div className="absolute top-[12%] left-[5%] size-72 landing-light-blob-purple landing-light-blob" />
            <div className="absolute top-[26%] right-[4%] size-80 landing-light-blob-indigo landing-light-blob" />
            <div className="absolute bottom-[-8%] left-[42%] size-64 landing-light-blob-blue landing-light-blob" />
          </div>
          <div className="relative z-10 mx-auto max-w-4xl text-center">
            <Badge
              variant="outline"
              className="mb-7 h-7 border-primary/30 bg-primary/10 px-3 text-indigo-200 shadow-lg shadow-primary/10"
            >
              <SparklesIcon data-icon="inline-start" />
              Personal AI Knowledge Workspace
            </Badge>
            <h1 className="landing-hero-headline text-4xl leading-[1.05] font-semibold tracking-[-0.045em] text-balance sm:text-6xl lg:text-7xl">
              <span data-headline-line className="block">
                Turn Your Documents
              </span>
              <span data-headline-line className="block">
                Into{" "}
                <span className="bg-gradient-to-r from-indigo-300 via-violet-300 to-fuchsia-300 bg-clip-text text-transparent">
                  Intelligence.
                </span>
              </span>
            </h1>
            <p className="mx-auto mt-7 max-w-2xl text-base leading-7 text-pretty text-muted-foreground sm:text-lg sm:leading-8">
              Upload documents. Organize them into notebooks. Chat with your own
              knowledge. Generate reports, flashcards, quizzes and mind maps—all
              from one intelligent workspace.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button
                data-magnetic
                size="lg"
                className="w-full border border-indigo-400/30 bg-indigo-600 text-white shadow-xl shadow-indigo-600/30 hover:bg-indigo-500 hover:shadow-indigo-500/40 sm:w-auto"
                nativeButton={false}
                render={<Link to="/register" />}
              >
                Get Started
                <ArrowRightIcon
                  data-icon="inline-end"
                  className="transition-transform duration-300 group-hover/button:translate-x-0.5"
                />
              </Button>
              <Button
                data-magnetic
                size="lg"
                variant="outline"
                className="w-full border-white/25 bg-white/10 text-white shadow-lg shadow-black/20 backdrop-blur-sm hover:border-indigo-300/50 hover:bg-white/15 hover:text-white sm:w-auto"
                nativeButton={false}
                render={<Link to="/login" />}
              >
                Sign In
              </Button>
            </div>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
              {[
                "Private workspace",
                "Source-grounded answers",
                "Built for deep work",
              ].map((item) => (
                <span key={item} className="flex items-center gap-1.5">
                  <CheckIcon className="size-3.5 text-indigo-300" />
                  {item}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section
          id="workspace"
          data-reveal
          className="landing-reveal scroll-mt-16 py-20 sm:py-28"
        >
          <SectionHeading
            eyebrow="Your knowledge, in context"
            title="A workspace designed for thinking"
            description="Sources, grounded AI conversation, and creative tools—together in one focused notebook."
          />
          <div className="mt-12 sm:mt-16">
            <ProductPreview />
          </div>
        </section>

        <section
          id="workflow"
          data-reveal
          className="landing-reveal scroll-mt-16 border-y border-white/5 bg-white/[0.015] py-20 sm:py-24"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="One continuous workflow"
              title="From scattered files to clear answers"
              description="A focused workflow that transforms documents into actionable knowledge."
            />
            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {workflow.map((item, index) => {
                const Icon = item.icon
                return (
                  <div key={item.title} data-reveal-child className="relative">
                    <Card className="landing-spotlight-card relative z-10 h-full border border-white/8 bg-white/[0.035] transition duration-300 hover:-translate-y-1 hover:border-primary/30 hover:bg-white/[0.055]">
                      <CardHeader>
                        <div className="mb-5 flex items-center justify-between">
                          <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/15 text-indigo-300 ring-1 ring-primary/25">
                            <Icon className="size-5" />
                          </span>
                          <span className="text-xs font-medium tracking-widest text-white/25">
                            {item.step}
                          </span>
                        </div>
                        <CardTitle className="text-lg">{item.title}</CardTitle>
                        <CardDescription className="leading-6">
                          {item.description}
                        </CardDescription>
                        {index === 0 ? (
                          <AnimatedUpload className="mt-5 w-full" />
                        ) : null}
                        {index === 1 ? (
                          <AnimatedKnowledgeGraph className="mt-5 w-full" />
                        ) : null}
                        {index === 2 ? (
                          <AnimatedAsk className="mt-5 w-full" />
                        ) : null}
                      </CardHeader>
                    </Card>
                    {index < workflow.length - 1 ? (
                      <span
                        aria-hidden="true"
                        className="landing-workflow-connector"
                      />
                    ) : null}
                  </div>
                )
              })}
            </div>
          </div>
        </section>

        <section
          id="features"
          data-reveal
          className="landing-reveal scroll-mt-16 border-y border-white/5 bg-white/[0.015] py-20 sm:py-28"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="Focused by design"
              title="Everything you need to work with your knowledge"
              description="Aviary keeps research, retrieval, and synthesis together in one calm workspace."
            />
            <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {features.map((feature) => {
                const Icon = feature.icon
                const Illustration = feature.illustration
                return (
                  <Card
                    key={feature.title}
                    data-reveal-child
                    data-spotlight-card
                    className="group landing-spotlight-card min-h-52 border border-white/8 bg-gradient-to-br from-white/[0.055] to-white/[0.02] transition-[transform,border-color,background-color,box-shadow] duration-500 ease-out hover:-translate-y-1 hover:border-primary/40 hover:shadow-xl hover:shadow-primary/10"
                  >
                    <CardHeader>
                      <span className="mb-7 flex size-12 items-center justify-center rounded-2xl bg-white/5 text-indigo-300 ring-1 ring-white/10 transition group-hover:scale-105 group-hover:bg-primary/15 group-hover:ring-primary/30">
                        <Icon className="size-5 transition-transform duration-500 group-hover:rotate-[4deg]" />
                      </span>
                      <CardTitle className="text-lg">{feature.title}</CardTitle>
                      <CardDescription className="max-w-lg leading-6">
                        {feature.description}
                      </CardDescription>
                      <Illustration className="landing-feature-illustration mt-6 w-full" />
                    </CardHeader>
                  </Card>
                )
              })}
            </div>
          </div>
        </section>

        <section
          id="studio"
          data-reveal
          className="landing-reveal scroll-mt-16 py-20 sm:py-28"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid items-center gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-20">
              <div>
                <Badge
                  variant="outline"
                  className="border-primary/25 bg-primary/10 text-indigo-200"
                >
                  <LightbulbIcon data-icon="inline-start" />
                  AI Studio
                </Badge>
                <h2 className="landing-headline mt-5 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
                  Transform knowledge into learning.
                </h2>
                <p className="mt-5 max-w-xl leading-7 text-pretty text-muted-foreground">
                  Generate interactive study tools and polished outputs grounded
                  in the sources inside your notebook.
                </p>
                <div className="mt-8 flex items-center gap-3 text-sm text-white/65">
                  <GitForkIcon className="size-4 text-indigo-300" />
                  One source library, many ways to understand it.
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {reports.map((report) => {
                  const Icon = report.icon
                  return (
                    <Card
                      key={report.title}
                      size="sm"
                      data-reveal-child
                      className="group landing-spotlight-card border border-white/8 bg-white/[0.035] transition duration-300 hover:-translate-y-1 hover:border-white/15 hover:bg-white/[0.06]"
                    >
                      <CardContent className="flex min-h-32 flex-col justify-between">
                        {report.title === "Study Guide" ? (
                          <AnimatedStudyGuide className="w-full" />
                        ) : report.title === "Mind Map" ? (
                          <AnimatedMindMap className="w-full" />
                        ) : report.title === "Flashcards" ? (
                          <AnimatedFlashcards className="w-full" />
                        ) : report.title === "Quiz" ? (
                          <AnimatedQuiz className="w-full" />
                        ) : report.title === "Briefing" ? (
                          <AnimatedReport className="w-full" />
                        ) : report.title === "Blog Draft" ? (
                          <AnimatedBlogDraft className="w-full" />
                        ) : (
                          <Icon
                            className={`size-5 transition-transform duration-500 group-hover:rotate-[4deg] ${report.color}`}
                          />
                        )}
                        <span className="text-sm font-medium">
                          {report.title}
                        </span>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </div>
          </div>
        </section>

        <section
          data-reveal
          className="landing-reveal px-4 pb-20 sm:px-6 sm:pb-28 lg:px-8"
        >
          <div className="relative isolate mx-auto max-w-7xl overflow-hidden rounded-[32px] border border-primary/20 bg-primary/10 px-6 py-16 text-center shadow-2xl shadow-primary/10 sm:px-12 sm:py-20">
            <div className="pointer-events-none absolute inset-0 z-0 landing-grid" />
            <div className="pointer-events-none absolute inset-x-0 -top-48 z-0 mx-auto h-80 max-w-2xl rounded-full bg-primary/25 blur-3xl" />
            <div className="relative z-10">
              <span className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-primary/20 text-indigo-200 ring-1 ring-primary/30">
                <BrainCircuitIcon className="size-6" />
              </span>
              <h2 className="mt-6 text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
                Build your personal AI knowledge base today.
              </h2>
              <p className="mx-auto mt-5 max-w-2xl leading-7 text-pretty text-muted-foreground">
                Start with a notebook. Upload your documents. Ask anything.
              </p>
              <Button
                data-magnetic
                size="lg"
                className="mt-8 border border-indigo-400/30 bg-indigo-600 text-white shadow-xl shadow-indigo-600/30 hover:bg-indigo-500 hover:shadow-indigo-500/40"
                nativeButton={false}
                render={<Link to="/register" />}
              >
                Create Account
                <ArrowRightIcon
                  data-icon="inline-end"
                  className="transition-transform duration-300 group-hover/button:translate-x-0.5"
                />
              </Button>
              <Button
                data-magnetic
                size="lg"
                variant="outline"
                className="mt-3 ml-0 border-white/25 bg-white/10 text-white shadow-lg shadow-black/20 hover:border-indigo-300/50 hover:bg-white/15 hover:text-white sm:mt-8 sm:ml-3"
                nativeButton={false}
                render={<Link to="/login" />}
              >
                Sign In
              </Button>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/5">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span>Aviary — Personal AI Knowledge Workspace</span>
          <div className="flex items-center gap-5">
            <Link
              to="/login"
              className="landing-text-link transition-colors hover:text-foreground"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="landing-text-link transition-colors hover:text-foreground"
            >
              Create Account
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
      <p className="text-xs font-semibold tracking-[0.18em] text-indigo-300 uppercase">
        {eyebrow}
      </p>
      <h2 className="landing-headline mt-4 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      <p className="mx-auto mt-4 max-w-2xl leading-7 text-pretty text-muted-foreground">
        {description}
      </p>
    </div>
  )
}
