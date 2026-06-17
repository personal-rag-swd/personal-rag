import { cn } from "@/lib/utils"

type AviaryLogoProps = {
  className?: string
  title?: string
  wordmark?: boolean
}

export function AviaryLogo({ className, title = "Aviary" }: AviaryLogoProps) {
  return (
    <img
      src="/aviary_logo.png"
      alt={title}
      className={cn("h-auto w-auto", className)}
      loading="eager"
      decoding="async"
    />
  )
}
