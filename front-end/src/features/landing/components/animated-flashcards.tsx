import type { HTMLAttributes } from "react"

import { cn } from "@/lib/utils"

const cards = ["card-1", "card-2", "card-3", "card-4"] as const

export function AnimatedFlashcards({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="img"
      aria-label="A stack of AI-generated flashcards flipping one at a time"
      className={cn("animated-flashcards", className)}
      {...props}
    >
      {cards.map((card) => (
        <div key={card} className={cn("animated-flashcards__card", card)}>
          <div className="animated-flashcards__face animated-flashcards__front">
            <span className="animated-flashcards__eyebrow" />
            <span className="animated-flashcards__line line-long" />
            <span className="animated-flashcards__line line-short" />
          </div>
          <div className="animated-flashcards__face animated-flashcards__back">
            <span>?</span>
          </div>
        </div>
      ))}
    </div>
  )
}
