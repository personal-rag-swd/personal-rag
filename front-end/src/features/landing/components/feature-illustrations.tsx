import { useId, type ReactNode, type SVGProps } from "react"

import { cn } from "@/lib/utils"

type IllustrationProps = SVGProps<SVGSVGElement>

function IllustrationFrame({
  label,
  variant,
  className,
  children,
  ...props
}: IllustrationProps & {
  label: string
  variant: string
  children: ReactNode
}) {
  const titleId = useId()

  return (
    <svg
      viewBox="0 0 320 150"
      role="img"
      aria-labelledby={titleId}
      className={cn("feature-illustration", variant, className)}
      {...props}
    >
      <title id={titleId}>{label}</title>
      {children}
    </svg>
  )
}

export function AnimatedNotebook(props: IllustrationProps) {
  return (
    <IllustrationFrame
      label="Connected notebook workspaces organizing knowledge"
      variant="animated-feature-notebook"
      {...props}
    >
      <g className="notebook-panels" aria-hidden="true">
        <rect
          className="panel-back"
          x="83"
          y="31"
          width="142"
          height="88"
          rx="8"
        />
        <rect
          className="panel-middle"
          x="72"
          y="39"
          width="154"
          height="88"
          rx="8"
        />
        <rect
          className="panel-front"
          x="61"
          y="47"
          width="166"
          height="88"
          rx="8"
        />
      </g>
      <g className="notebook-tabs" aria-hidden="true">
        <path pathLength="1" d="M82 47V32h35M141 47V25h38M199 47V34h35" />
        <circle cx="117" cy="32" r="4" />
        <circle cx="179" cy="25" r="4" />
        <circle cx="234" cy="34" r="4" />
      </g>
      <g className="notebook-lines" aria-hidden="true">
        <path pathLength="1" d="M83 72h102M83 87h122M83 102h75" />
      </g>
      <circle
        className="notebook-pulse"
        cx="179"
        cy="25"
        r="10"
        aria-hidden="true"
      />
    </IllustrationFrame>
  )
}

export function AnimatedProcessing(props: IllustrationProps) {
  return (
    <IllustrationFrame
      label="Documents splitting into indexed knowledge chunks"
      variant="animated-feature-processing"
      {...props}
    >
      <g className="processing-pages" aria-hidden="true">
        <path className="page-1" d="M43 37h47l10 10v67H43zM90 37v10h10" />
        <path className="page-2" d="M60 29h47l10 10v67H60zM107 29v10h10" />
        <path className="page-3" d="M77 21h47l10 10v67H77zM124 21v10h10" />
      </g>
      <g className="processing-chunks" aria-hidden="true">
        <path
          pathLength="1"
          d="M151 45h42m8 0h29M151 61h25m8 0h55M151 77h51m8 0h34M151 93h32m8 0h45"
        />
      </g>
      <g className="processing-flow" aria-hidden="true">
        <path
          pathLength="1"
          d="M132 60c12 0 10-15 19-15M132 60c12 0 10 17 19 17M244 77c16 0 17 16 27 16"
        />
      </g>
      <g className="processing-node" aria-hidden="true">
        <circle cx="274" cy="93" r="14" />
        <circle cx="274" cy="93" r="4" />
      </g>
    </IllustrationFrame>
  )
}

export function AnimatedStudio(props: IllustrationProps) {
  return (
    <IllustrationFrame
      label="AI Studio generating several learning outputs"
      variant="animated-feature-studio"
      {...props}
    >
      <g className="studio-tile tile-1" aria-hidden="true">
        <rect x="61" y="25" width="82" height="44" rx="7" />
        <path d="M82 50h39M91 42l9 8 11-15" />
      </g>
      <g className="studio-tile tile-2" aria-hidden="true">
        <rect x="177" y="25" width="82" height="44" rx="7" />
        <circle cx="218" cy="43" r="5" />
        <path d="M218 48v9m0-14-14 13m14-13 14 13" />
      </g>
      <g className="studio-tile tile-3" aria-hidden="true">
        <rect x="61" y="82" width="82" height="44" rx="7" />
        <rect x="84" y="95" width="34" height="20" rx="3" />
        <path d="M89 102h24m-24 6h17" />
      </g>
      <g className="studio-tile tile-4" aria-hidden="true">
        <rect x="177" y="82" width="82" height="44" rx="7" />
        <path d="M198 113V99m10 14V93m10 20v-9m10 9V96" />
      </g>
    </IllustrationFrame>
  )
}

export function AnimatedSearch(props: IllustrationProps) {
  return (
    <IllustrationFrame
      label="Semantic search scanning knowledge and finding a match"
      variant="animated-feature-search"
      {...props}
    >
      <g className="search-lines" aria-hidden="true">
        <path d="M55 43h184M55 65h143M55 87h202M55 109h162" />
      </g>
      <path className="search-match" d="M55 87h202" aria-hidden="true" />
      <g className="search-lens" aria-hidden="true">
        <circle cx="78" cy="73" r="23" />
        <path d="m94 90 18 18" />
      </g>
      <circle
        className="search-pulse"
        cx="211"
        cy="87"
        r="11"
        aria-hidden="true"
      />
    </IllustrationFrame>
  )
}

export function AnimatedPrivacy(props: IllustrationProps) {
  return (
    <IllustrationFrame
      label="A secure private knowledge boundary protected by a lock"
      variant="animated-feature-privacy"
      {...props}
    >
      <path
        className="privacy-shield"
        pathLength="1"
        d="M160 19c27 17 51 17 67 18v37c0 30-25 48-67 62-42-14-67-32-67-62V37c16-1 40-1 67-18Z"
        aria-hidden="true"
      />
      <g className="privacy-lock" aria-hidden="true">
        <rect x="142" y="68" width="36" height="29" rx="6" />
        <path d="M149 68v-9c0-7 5-12 11-12s11 5 11 12v9M160 79v8" />
      </g>
      <g className="privacy-dots" aria-hidden="true">
        <circle cx="124" cy="62" r="3" />
        <circle cx="126" cy="97" r="3" />
        <circle cx="196" cy="62" r="3" />
        <circle cx="194" cy="97" r="3" />
      </g>
      <path
        className="privacy-pulse"
        d="M160 29c22 13 41 14 54 15v28c0 23-19 37-54 49"
        aria-hidden="true"
      />
    </IllustrationFrame>
  )
}
