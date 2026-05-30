import type { LucideIcon } from "lucide-react";
import {
  AudioLinesIcon,
  BarChart3Icon,
  BrainCircuitIcon,
  FileQuestionIcon,
  ImagesIcon,
  LayoutPanelTopIcon,
  Rows3Icon,
  SquareStackIcon,
  VideoIcon,
} from "lucide-react";

export type StudioAction = {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

export const STUDIO_ACTIONS: StudioAction[] = [
  {
    id: "audio-overview",
    label: "Audio Overview",
    description: "Create a narrated summary.",
    icon: AudioLinesIcon,
  },
  {
    id: "slide-deck",
    label: "Slide Deck",
    description: "Turn notes into slides.",
    icon: LayoutPanelTopIcon,
  },
  {
    id: "video-overview",
    label: "Video Overview",
    description: "Draft a video outline.",
    icon: VideoIcon,
  },
  {
    id: "mind-map",
    label: "Mind Map",
    description: "Map source concepts.",
    icon: BrainCircuitIcon,
  },
  {
    id: "reports",
    label: "Reports",
    description: "Generate a report.",
    icon: BarChart3Icon,
  },
  {
    id: "flashcards",
    label: "Flashcards",
    description: "Build review cards.",
    icon: SquareStackIcon,
  },
  {
    id: "quiz",
    label: "Quiz",
    description: "Create practice questions.",
    icon: FileQuestionIcon,
  },
  {
    id: "infographic",
    label: "Infographic",
    description: "Extract visual points.",
    icon: ImagesIcon,
  },
  {
    id: "data-table",
    label: "Data Table",
    description: "Structure key facts.",
    icon: Rows3Icon,
  },
];
