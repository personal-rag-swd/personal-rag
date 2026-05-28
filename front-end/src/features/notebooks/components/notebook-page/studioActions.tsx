import * as React from "react";
import {
  AudioLinesIcon,
  BarChart3Icon,
  BrainCircuitIcon,
  FileTextIcon,
  HelpCircleIcon,
  SlidersIcon,
  TableIcon,
  VideoIcon,
  ZapIcon,
} from "lucide-react";

export type StudioAction = {
  id: string;
  label: string;
  icon: React.ReactNode;
  colorClass: string;
};

export const STUDIO_ACTIONS: StudioAction[] = [
  {
    id: "audio-overview",
    label: "Audio Overview",
    icon: <AudioLinesIcon className="size-4" />,
    colorClass: "text-amber-500 bg-amber-500/10 border-amber-500/20",
  },
  {
    id: "slide-deck",
    label: "Slide Deck",
    icon: <SlidersIcon className="size-4" />,
    colorClass: "text-lime-500 bg-lime-500/10 border-lime-500/20",
  },
  {
    id: "video-overview",
    label: "Video Overview",
    icon: <VideoIcon className="size-4" />,
    colorClass: "text-sky-500 bg-sky-500/10 border-sky-500/20",
  },
  {
    id: "mind-map",
    label: "Mind Map",
    icon: <BrainCircuitIcon className="size-4" />,
    colorClass: "text-pink-500 bg-pink-500/10 border-pink-500/20",
  },
  {
    id: "reports",
    label: "Reports",
    icon: <BarChart3Icon className="size-4" />,
    colorClass: "text-blue-500 bg-blue-500/10 border-blue-500/20",
  },
  {
    id: "flashcards",
    label: "Flashcards",
    icon: <ZapIcon className="size-4" />,
    colorClass: "text-orange-400 bg-orange-400/10 border-orange-400/20",
  },
  {
    id: "quiz",
    label: "Quiz",
    icon: <HelpCircleIcon className="size-4" />,
    colorClass: "text-violet-500 bg-violet-500/10 border-violet-500/20",
  },
  {
    id: "infographic",
    label: "Infographic",
    icon: <FileTextIcon className="size-4" />,
    colorClass: "text-teal-500 bg-teal-500/10 border-teal-500/20",
  },
  {
    id: "data-table",
    label: "Data Table",
    icon: <TableIcon className="size-4" />,
    colorClass: "text-indigo-500 bg-indigo-500/10 border-indigo-500/20",
  },
];
