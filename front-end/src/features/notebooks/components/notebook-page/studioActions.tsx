import type { LucideIcon } from "lucide-react"
import {
  BarChart3Icon,
  BrainCircuitIcon,
  FileQuestionIcon,
  SquareStackIcon,
} from "lucide-react"

export type StudioAction = {
  id: string
  label: string
  description: string
  icon: LucideIcon
  implemented: boolean
}

const ALL_STUDIO_ACTIONS: StudioAction[] = [
  {
    id: "mind-map",
    label: "Mind Map",
    description: "Map concepts",
    icon: BrainCircuitIcon,
    implemented: true,
  },
  {
    id: "reports",
    label: "Reports",
    description: "Data analysis",
    icon: BarChart3Icon,
    implemented: true,
  },
  // TODO: Planned actions (Audio Overview, Slide Deck, Video Draft) go here with
  // `implemented: false` once built — they render disabled and sort last.
  {
    id: "flashcards",
    label: "Flashcards",
    description: "Review cards",
    icon: SquareStackIcon,
    implemented: true,
  },
  {
    id: "quiz",
    label: "Quiz",
    description: "Practice questions",
    icon: FileQuestionIcon,
    implemented: true,
  },
]

export const STUDIO_ACTIONS: StudioAction[] = [
  ...ALL_STUDIO_ACTIONS.filter((a) => a.implemented),
  ...ALL_STUDIO_ACTIONS.filter((a) => !a.implemented),
]
