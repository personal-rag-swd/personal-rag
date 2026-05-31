import {
  FileTextIcon,
  GraduationCapIcon,
  NewspaperIcon,
  PenLineIcon,
} from "lucide-react";

import type { ReportType } from "@/features/notebooks/types";

export type ReportTypeMeta = {
  id: ReportType;
  label: string;
  shortLabel: string;
  description: string;
  icon: React.ReactNode;
  colorClass: string;
  placeholder: string;
};

export const REPORT_TYPES: ReportTypeMeta[] = [
  {
    id: "custom",
    label: "Create Your Own",
    shortLabel: "Create Your Own",
    description: "Describe exactly what you want — get a custom markdown report.",
    icon: <PenLineIcon className="size-4" />,
    colorClass: "text-amber-500 bg-amber-500/10 border-amber-500/20",
    placeholder: "What do you want to generate? (e.g., Write a newsletter about the key trends mentioned in the sources.)",
  },
  {
    id: "briefing",
    label: "Briefing Doc",
    shortLabel: "Briefing Doc",
    description: "Executive summary, key takeaways, and strategic implications.",
    icon: <FileTextIcon className="size-4" />,
    colorClass: "text-blue-500 bg-blue-500/10 border-blue-500/20",
    placeholder: "Any specific focus or requirements for this briefing? (Optional)",
  },
  {
    id: "study_guide",
    label: "Study Guide",
    shortLabel: "Study Guide",
    description: "Glossary plus multiple-choice quiz with explanations.",
    icon: <GraduationCapIcon className="size-4" />,
    colorClass: "text-violet-500 bg-violet-500/10 border-violet-500/20",
    placeholder: "Any specific focus or requirements for this study guide? (Optional)",
  },
  {
    id: "blog",
    label: "Blog Post",
    shortLabel: "Blog Post",
    description: "Engaging article in markdown, ready to publish.",
    icon: <NewspaperIcon className="size-4" />,
    colorClass: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
    placeholder: "Any specific focus, tone, or angle for this blog post? (Optional)",
  },
];

export const REPORT_TYPE_BY_ID = Object.fromEntries(
  REPORT_TYPES.map((t) => [t.id, t])
) as Record<ReportType, ReportTypeMeta>;
