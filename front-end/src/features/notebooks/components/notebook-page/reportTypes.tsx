import {
  FileQuestionIcon,
  FileTextIcon,
  GraduationCapIcon,
  NewspaperIcon,
  PenLineIcon,
  GitForkIcon,
  SquareStackIcon,
} from "lucide-react"

import type { ReportType } from "@/features/notebooks/types"

export type ReportTypeMeta = {
  id: ReportType
  label: string
  shortLabel: string
  description: string
  icon: React.ReactNode
  placeholder: string
}

export const REPORT_TYPES: ReportTypeMeta[] = [
  {
    id: "custom",
    label: "Create Your Own",
    shortLabel: "Create Your Own",
    description:
      "Describe exactly what you want — get a custom markdown report.",
    icon: <PenLineIcon className="size-4" />,
    placeholder:
      "What do you want to generate? (e.g., Write a newsletter about the key trends mentioned in the sources.)",
  },
  {
    id: "briefing",
    label: "Briefing Doc",
    shortLabel: "Briefing Doc",
    description:
      "Executive summary, key takeaways, and strategic implications.",
    icon: <FileTextIcon className="size-4" />,
    placeholder:
      "Any specific focus or requirements for this briefing? (Optional)",
  },
  {
    id: "study_guide",
    label: "Study Guide",
    shortLabel: "Study Guide",
    description: "Glossary plus multiple-choice quiz with explanations.",
    icon: <GraduationCapIcon className="size-4" />,
    placeholder:
      "Any specific focus or requirements for this study guide? (Optional)",
  },
  {
    id: "blog",
    label: "Blog Post",
    shortLabel: "Blog Post",
    description: "Engaging article in markdown, ready to publish.",
    icon: <NewspaperIcon className="size-4" />,
    placeholder:
      "Any specific focus, tone, or angle for this blog post? (Optional)",
  },
]

export const REPORT_TYPE_BY_ID = {
  ...Object.fromEntries(REPORT_TYPES.map((t) => [t.id, t])),
  mindmap: {
    id: "mindmap" as ReportType,
    label: "Mind Map",
    shortLabel: "Mind Map",
    description: "Visual concept map and semantic relationship graph.",
    icon: <GitForkIcon className="size-4" />,
    placeholder: "",
  },
  quiz: {
    id: "quiz" as ReportType,
    label: "Quiz",
    shortLabel: "Quiz",
    description: "Interactive multiple-choice quiz with scoring.",
    icon: <FileQuestionIcon className="size-4" />,
    placeholder: "",
  },
  flashcards: {
    id: "flashcards" as ReportType,
    label: "Flashcards",
    shortLabel: "Flashcards",
    description: "Study cards you flip to review key concepts.",
    icon: <SquareStackIcon className="size-4" />,
    placeholder: "",
  },
  note: {
    id: "note" as ReportType,
    label: "Note",
    shortLabel: "Note",
    description: "Your custom notes saved in this workspace.",
    icon: <PenLineIcon className="size-4" />,
    placeholder: "",
  },
} as Record<ReportType, ReportTypeMeta>
