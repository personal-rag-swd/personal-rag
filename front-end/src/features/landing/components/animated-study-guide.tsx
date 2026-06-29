import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedStudyGuide({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const titleId = useId()

  return (
    <svg
      viewBox="0 0 180 90"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-study-guide", className)}
      {...props}
    >
      <title id={titleId}>
        A structured notebook organizing chapters into a study guide
      </title>

      <path
        className="study-guide-outline"
        pathLength="1"
        d="M39 13h107v65H39zM51 13v65M35 25h8m-8 14h8m-8 14h8m-8 14h8"
        aria-hidden="true"
      />

      <g className="study-guide-long-lines" aria-hidden="true">
        <path pathLength="1" d="M59 20h75v14H59z" className="line-1" />
        <path pathLength="1" d="M59 39h75v14H59z" className="line-2" />
        <path pathLength="1" d="M59 58h75v14H59z" className="line-3" />
      </g>

      <g className="study-guide-short-lines" aria-hidden="true">
        <path pathLength="1" d="M70 25h48m-48 4h33" />
        <path pathLength="1" d="M70 44h53m-53 4h39" />
        <path pathLength="1" d="M70 63h42m-42 4h50" />
      </g>

      <g className="study-guide-bullets" aria-hidden="true">
        <circle className="bullet-1" cx="64" cy="25" r="2" />
        <circle className="bullet-2" cx="64" cy="44" r="2" />
        <circle className="bullet-3" cx="64" cy="63" r="2" />
      </g>

      <path
        className="study-guide-highlight"
        d="M69 44h55"
        aria-hidden="true"
      />
      <path
        className="study-guide-sparkle"
        d="m145 27 2 4.5 4.5 2-4.5 2-2 4.5-2-4.5-4.5-2 4.5-2z"
        aria-hidden="true"
      />
    </svg>
  )
}
