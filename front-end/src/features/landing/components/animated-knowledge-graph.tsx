import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedKnowledgeGraph({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const titleId = useId()
  const glowId = `${titleId.replaceAll(":", "")}GraphGlow`

  return (
    <svg
      viewBox="0 0 320 180"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-knowledge-graph", className)}
      {...props}
    >
      <title id={titleId}>
        Semantic connections forming an intelligent knowledge graph
      </title>
      <defs>
        <filter id={glowId} x="-150%" y="-150%" width="400%" height="400%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g className="animated-knowledge-graph__lines" aria-hidden="true">
        <path pathLength="1" d="M160 90 82 46" />
        <path pathLength="1" d="M160 90 237 42" />
        <path pathLength="1" d="M160 90 268 105" />
        <path pathLength="1" d="M160 90 222 143" />
        <path pathLength="1" d="M160 90 90 139" />
        <path pathLength="1" d="M160 90 49 91" />
      </g>

      <g className="animated-knowledge-graph__nodes" aria-hidden="true">
        <circle
          className="animated-knowledge-graph__node node-1"
          cx="82"
          cy="46"
          r="8"
        />
        <circle
          className="animated-knowledge-graph__node node-2"
          cx="237"
          cy="42"
          r="10"
        />
        <circle
          className="animated-knowledge-graph__node node-3"
          cx="268"
          cy="105"
          r="7"
        />
        <circle
          className="animated-knowledge-graph__node node-4"
          cx="222"
          cy="143"
          r="8"
        />
        <circle
          className="animated-knowledge-graph__node node-5"
          cx="90"
          cy="139"
          r="10"
        />
        <circle
          className="animated-knowledge-graph__node node-6"
          cx="49"
          cy="91"
          r="7"
        />
      </g>

      <circle
        className="animated-knowledge-graph__focus"
        cx="237"
        cy="42"
        r="14"
        filter={`url(#${glowId})`}
        aria-hidden="true"
      />

      <g className="animated-knowledge-graph__center" aria-hidden="true">
        <circle cx="160" cy="90" r="21" filter={`url(#${glowId})`} />
        <circle
          cx="160"
          cy="90"
          r="8"
          className="animated-knowledge-graph__core"
        />
      </g>

      <circle
        className="animated-knowledge-graph__pulse pulse-1"
        r="3"
        aria-hidden="true"
      />
      <circle
        className="animated-knowledge-graph__pulse pulse-2"
        r="2.5"
        aria-hidden="true"
      />
      <circle
        className="animated-knowledge-graph__pulse pulse-3"
        r="2.5"
        aria-hidden="true"
      />
    </svg>
  )
}
