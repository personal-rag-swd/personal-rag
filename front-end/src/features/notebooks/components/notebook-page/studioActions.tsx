import type { LucideIcon } from "lucide-react"
import {
  AudioLinesIcon,
  BarChart3Icon,
  BrainCircuitIcon,
  FileQuestionIcon,
  LayoutPanelTopIcon,
  SquareStackIcon,
  VideoIcon,
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
  {
    id: "audio-overview",
    label: "Audio Overview",
    description: "Narrated summary",
    icon: AudioLinesIcon,
    implemented: false,
  },
  {
    id: "slide-deck",
    label: "Slide Deck",
    description: "Notes into slides",
    icon: LayoutPanelTopIcon,
    implemented: false,
  },
  {
    id: "video-draft",
    label: "Video Draft",
    description: "Video outline",
    icon: VideoIcon,
    implemented: false,
  },
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
