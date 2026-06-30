import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedReport({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const titleId = useId()

  return (
    <svg
      viewBox="0 0 180 90"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-report", className)}
      {...props}
    >
      <title id={titleId}>
        An executive briefing dashboard with charts and key insights
      </title>

      <g className="animated-report__outline" aria-hidden="true">
        <rect pathLength="1" x="19" y="12" width="142" height="66" rx="8" />
        <path pathLength="1" d="M19 28h142" />
        <circle cx="30" cy="20" r="2" />
        <circle cx="38" cy="20" r="2" />
      </g>

      <g className="animated-report__text" aria-hidden="true">
        <path pathLength="1" d="M29 36h37v15H29z" className="text-line-1" />
        <path pathLength="1" d="M72 36h37v15H72z" className="text-line-2" />
        <path pathLength="1" d="M115 36h36v15h-36z" className="text-line-3" />
      </g>

      <g className="animated-report__bars" aria-hidden="true">
        <rect className="bar-1" x="30" y="62" width="7" height="9" rx="1" />
        <rect className="bar-2" x="40" y="57" width="7" height="14" rx="1" />
        <rect className="bar-3" x="50" y="54" width="7" height="17" rx="1" />
      </g>

      <g className="animated-report__chart" aria-hidden="true">
        <path pathLength="1" d="M72 69 88 61l14 5 15-11 14 4 18-7" />
        <circle cx="88" cy="61" r="1.5" />
        <circle cx="102" cy="66" r="1.5" />
        <circle cx="117" cy="55" r="1.5" />
        <circle cx="131" cy="59" r="1.5" />
        <circle cx="149" cy="52" r="1.5" />
      </g>

      <g className="animated-report__summary" aria-hidden="true">
        <circle cx="143" cy="43.5" r="4" />
        <path d="m141 43.5 1.5 1.5 3-3" />
      </g>
    </svg>
  )
}
