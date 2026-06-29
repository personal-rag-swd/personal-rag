import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedQuiz({ className, ...props }: SVGProps<SVGSVGElement>) {
  const titleId = useId()

  return (
    <svg
      viewBox="0 0 180 90"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-quiz", className)}
      {...props}
    >
      <title id={titleId}>
        AI-generated quiz answers being evaluated in sequence
      </title>

      <g className="animated-quiz__options" aria-hidden="true">
        <g className="animated-quiz__option option-1">
          <circle cx="25" cy="20" r="7" />
          <path d="M43 17h92M43 23h63" />
        </g>
        <g className="animated-quiz__option option-2">
          <circle cx="25" cy="45" r="7" />
          <path d="M43 42h108M43 48h78" />
        </g>
        <g className="animated-quiz__option option-3">
          <circle cx="25" cy="70" r="7" />
          <path d="M43 67h82M43 73h54" />
        </g>
      </g>

      <circle
        className="animated-quiz__selection selection-1"
        cx="25"
        cy="20"
        r="11"
        aria-hidden="true"
      />
      <circle
        className="animated-quiz__selection selection-2"
        cx="25"
        cy="45"
        r="11"
        aria-hidden="true"
      />

      <g className="animated-quiz__checks" aria-hidden="true">
        <path className="check-1" pathLength="1" d="m20.5 20 3 3 6-7" />
        <path className="check-2" pathLength="1" d="m20.5 45 3 3 6-7" />
      </g>
    </svg>
  )
}
