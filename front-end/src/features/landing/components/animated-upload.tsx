import { useId, type SVGProps } from "react"

import { cn } from "@/lib/utils"

const documents = [
  { label: "PDF", className: "animated-upload__document--pdf" },
  { label: "DOC", className: "animated-upload__document--doc" },
  { label: "TXT", className: "animated-upload__document--txt" },
  { label: "MD", className: "animated-upload__document--md" },
] as const

export function AnimatedUpload({
  className,
  ...props
}: SVGProps<SVGSVGElement>) {
  const titleId = useId()
  const glowId = `${titleId.replaceAll(":", "")}Glow`

  return (
    <svg
      viewBox="0 0 320 180"
      role="img"
      aria-labelledby={titleId}
      className={cn("animated-upload", className)}
      {...props}
    >
      <title id={titleId}>
        Documents merging into one intelligent knowledge source
      </title>
      <defs>
        <filter id={glowId} x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g className="animated-upload__connections" aria-hidden="true">
        <path pathLength="1" d="M68 48 L160 90" />
        <path pathLength="1" d="M252 45 L160 90" />
        <path pathLength="1" d="M65 132 L160 90" />
        <path pathLength="1" d="M255 132 L160 90" />
      </g>

      {documents.map((document) => (
        <g
          key={document.label}
          className={cn("animated-upload__document", document.className)}
          aria-hidden="true"
        >
          <path d="M1 1h24l10 10v37H1z" />
          <path d="M25 1v10h10" />
          <path
            d="M8 19h19M8 25h19M8 31h13"
            className="animated-upload__detail"
          />
          <text x="18" y="42" textAnchor="middle">
            {document.label}
          </text>
        </g>
      ))}

      <g
        className="animated-upload__node"
        filter={`url(#${glowId})`}
        aria-hidden="true"
      >
        <circle className="animated-upload__pulse" cx="160" cy="90" r="30" />
        <circle cx="160" cy="90" r="22" />
        <path d="M150 86c0-5 3-9 8-9 3 0 5 1 7 4 4 0 7 3 7 7 0 3-2 6-5 7-1 5-5 8-10 7-4 0-7-3-7-7-3-1-5-4-5-7 0-3 2-6 5-7" />
        <path
          d="M156 83v14m8-14v14m-14-7h20"
          className="animated-upload__detail"
        />
      </g>
    </svg>
  )
}
