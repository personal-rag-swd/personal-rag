import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedMindMap({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const titleId = useId()
  const glowId = `${titleId.replaceAll(":", "")}MindMapGlow`

  return (
    <svg
      viewBox="0 0 180 90"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-mind-map", className)}
      {...props}
    >
      <title id={titleId}>
        An AI-generated mind map expanding from a central idea
      </title>
      <defs>
        <filter id={glowId} x="-200%" y="-200%" width="500%" height="500%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g className="animated-mind-map__primary-branches" aria-hidden="true">
        <path pathLength="1" d="M90 45C72 42 63 23 40 22" />
        <path pathLength="1" d="M90 45c18-3 28-23 50-25" />
        <path pathLength="1" d="M90 45C72 49 61 66 38 68" />
        <path pathLength="1" d="M90 45c18 4 29 23 52 25" />
      </g>

      <g className="animated-mind-map__secondary-branches" aria-hidden="true">
        <path pathLength="1" d="M140 20c10-1 14-8 25-10" />
        <path pathLength="1" d="M140 20c12 2 18 10 30 12" />
        <path pathLength="1" d="M38 68c-10-1-16-8-24-12" />
      </g>

      <g
        className="animated-mind-map__nodes"
        filter={`url(#${glowId})`}
        aria-hidden="true"
      >
        <circle
          className="animated-mind-map__node node-1"
          cx="40"
          cy="22"
          r="5"
        />
        <circle
          className="animated-mind-map__node node-2"
          cx="140"
          cy="20"
          r="6"
        />
        <circle
          className="animated-mind-map__node node-3"
          cx="38"
          cy="68"
          r="6"
        />
        <circle
          className="animated-mind-map__node node-4"
          cx="142"
          cy="70"
          r="5"
        />
        <circle
          className="animated-mind-map__node animated-mind-map__secondary-node node-5"
          cx="165"
          cy="10"
          r="3.5"
        />
        <circle
          className="animated-mind-map__node animated-mind-map__secondary-node node-6"
          cx="170"
          cy="32"
          r="3.5"
        />
        <circle
          className="animated-mind-map__node animated-mind-map__secondary-node node-7"
          cx="14"
          cy="56"
          r="3.5"
        />
      </g>

      <g
        className="animated-mind-map__center"
        filter={`url(#${glowId})`}
        aria-hidden="true"
      >
        <circle cx="90" cy="45" r="10" />
        <circle cx="90" cy="45" r="3" className="animated-mind-map__core" />
      </g>
    </svg>
  )
}
