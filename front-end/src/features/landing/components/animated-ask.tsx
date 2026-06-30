import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedAsk({ className, ...props }: SVGProps<SVGSVGElement>) {
  const titleId = useId()

  return (
    <svg
      viewBox="0 0 320 180"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-ask", className)}
      {...props}
    >
      <title id={titleId}>
        A question becoming a grounded answer with source citations
      </title>

      <g className="animated-ask__question" aria-hidden="true">
        <circle cx="61" cy="39" r="12" />
        <path d="M58 36c0-3 2-5 5-5s5 2 5 5c0 4-5 4-5 8m0 4h.01" />
        <path
          pathLength="1"
          d="M84 34h153M84 45h107"
          className="animated-ask__question-lines"
        />
      </g>

      <g className="animated-ask__thinking" aria-hidden="true">
        <circle className="dot-1" cx="148" cy="68" r="2" />
        <circle className="dot-2" cx="160" cy="68" r="2" />
        <circle className="dot-3" cx="172" cy="68" r="2" />
      </g>

      <g className="animated-ask__answer-mark" aria-hidden="true">
        <path d="m61 94 2.5 5.5L69 102l-5.5 2.5L61 110l-2.5-5.5L53 102l5.5-2.5z" />
      </g>

      <g className="animated-ask__answer" aria-hidden="true">
        <path pathLength="1" d="M84 93h137" className="answer-line-1" />
        <path pathLength="1" d="M84 110h169" className="answer-line-2" />
        <path pathLength="1" d="M84 127h119" className="answer-line-3" />
      </g>

      <g className="animated-ask__citations" aria-hidden="true">
        <g className="citation-1">
          <rect x="229" y="84" width="29" height="18" rx="9" />
          <text x="243.5" y="96" textAnchor="middle">
            01
          </text>
        </g>
        <g className="citation-2">
          <rect x="211" y="118" width="29" height="18" rx="9" />
          <text x="225.5" y="130" textAnchor="middle">
            02
          </text>
        </g>
      </g>
    </svg>
  )
}
