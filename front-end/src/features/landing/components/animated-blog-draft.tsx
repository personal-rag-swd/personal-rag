import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

export function AnimatedBlogDraft({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const titleId = useId()

  return (
    <svg
      viewBox="0 0 180 90"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-blog-draft", className)}
      {...props}
    >
      <title id={titleId}>AI writing a polished article line by line</title>

      <path
        className="blog-draft-outline"
        pathLength="1"
        d="M28 17h124M28 17v59M38 11h16m6 0h8"
        aria-hidden="true"
      />
      <path
        className="blog-draft-heading"
        pathLength="1"
        d="M42 29h65"
        aria-hidden="true"
      />
      <g className="blog-draft-lines" aria-hidden="true">
        <path className="line-1" pathLength="1" d="M42 43h98" />
        <path className="line-2" pathLength="1" d="M42 53h84" />
        <path className="line-3" pathLength="1" d="M42 63h104" />
        <path className="line-4" pathLength="1" d="M42 73h73" />
      </g>
      <path className="blog-draft-highlight" d="M41 32h68" aria-hidden="true" />
      <path className="blog-draft-cursor" d="M0 0v8" aria-hidden="true" />
    </svg>
  )
}
