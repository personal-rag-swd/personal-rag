import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedChat({ className, ...props }: SVGProps<SVGSVGElement>) {
  const titleId = useId()

  return (
    <svg
      viewBox="0 0 320 150"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-chat", className)}
      {...props}
    >
      <title id={titleId}>
        A grounded AI conversation with citations from source material
      </title>

      <g className="animated-chat__user" aria-hidden="true">
        <circle cx="265" cy="30" r="8" />
        <path pathLength="1" d="M111 30h132" />
        <path
          pathLength="1"
          d="M178 42h65"
          className="animated-chat__user-detail"
        />
      </g>

      <g className="animated-chat__thinking" aria-hidden="true">
        <circle className="dot-1" cx="50" cy="68" r="2" />
        <circle className="dot-2" cx="61" cy="68" r="2" />
        <circle className="dot-3" cx="72" cy="68" r="2" />
      </g>

      <g className="animated-chat__assistant-mark" aria-hidden="true">
        <path d="m49 86 2.5 5.5L57 94l-5.5 2.5L49 102l-2.5-5.5L41 94l5.5-2.5z" />
      </g>

      <g className="animated-chat__response" aria-hidden="true">
        <path pathLength="1" d="M73 86h148" className="response-line-1" />
        <path pathLength="1" d="M73 103h181" className="response-line-2" />
        <path pathLength="1" d="M73 120h126" className="response-line-3" />
      </g>

      <g className="animated-chat__citations" aria-hidden="true">
        <g className="citation-1">
          <rect x="229" y="77" width="30" height="18" rx="9" />
          <text x="244" y="89" textAnchor="middle">
            S1
          </text>
        </g>
        <g className="citation-2">
          <rect x="207" y="111" width="30" height="18" rx="9" />
          <text x="222" y="123" textAnchor="middle">
            S2
          </text>
        </g>
      </g>
    </svg>
  )
}
