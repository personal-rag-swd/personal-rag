import { useEffect } from "react"

export function LandingEffects() {
  useEffect(() => {
    document.documentElement.classList.add("landing-reveal-ready")
    const elements = document.querySelectorAll<HTMLElement>("[data-reveal]")
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches

    if (reduceMotion || !("IntersectionObserver" in window)) {
      elements.forEach((element) =>
        element.setAttribute("data-visible", "true")
      )
      return () =>
        document.documentElement.classList.remove("landing-reveal-ready")
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return
          entry.target.setAttribute("data-visible", "true")
          observer.unobserve(entry.target)
        })
      },
      { rootMargin: "0px 0px -12%", threshold: 0.12 }
    )

    elements.forEach((element) => observer.observe(element))

    const finePointer = window.matchMedia("(pointer: fine)").matches
    const hero = document.querySelector<HTMLElement>("[data-hero-motion]")
    const heroLayer = document.querySelector<HTMLElement>(
      "[data-hero-parallax]"
    )
    const spotlightCards = document.querySelectorAll<HTMLElement>(
      "[data-spotlight-card]"
    )
    const magneticButtons =
      document.querySelectorAll<HTMLElement>("[data-magnetic]")
    const preview = document.querySelector<HTMLElement>("[data-preview-tilt]")
    let frame = 0
    let pointerX = 0
    let pointerY = 0

    const resetTransform = (element: HTMLElement | null) => {
      if (element) element.style.transform = ""
    }

    const updateMotion = (event: PointerEvent) => {
      pointerX = event.clientX
      pointerY = event.clientY
      if (frame) return

      frame = window.requestAnimationFrame(() => {
        frame = 0
        const target = event.target
        if (!(target instanceof Element)) return

        if (hero?.contains(target) && heroLayer) {
          const rect = hero.getBoundingClientRect()
          const x = (pointerX - rect.left) / rect.width - 0.5
          const y = (pointerY - rect.top) / rect.height - 0.5
          heroLayer.style.transform = `translate3d(${x * 12}px, ${y * 8}px, 0)`
        }

        const card = target.closest<HTMLElement>("[data-spotlight-card]")
        if (card) {
          const rect = card.getBoundingClientRect()
          card.style.setProperty("--spotlight-x", `${pointerX - rect.left}px`)
          card.style.setProperty("--spotlight-y", `${pointerY - rect.top}px`)
        }

        const button = target.closest<HTMLElement>("[data-magnetic]")
        if (button) {
          const rect = button.getBoundingClientRect()
          const x = (pointerX - rect.left) / rect.width - 0.5
          const y = (pointerY - rect.top) / rect.height - 0.5
          button.style.transform = `translate3d(${x * 6}px, ${y * 5}px, 0)`
        }

        if (preview?.contains(target)) {
          const rect = preview.getBoundingClientRect()
          const x = (pointerX - rect.left) / rect.width - 0.5
          const y = (pointerY - rect.top) / rect.height - 0.5
          preview.style.transform = `perspective(1200px) rotateX(${-y * 4}deg) rotateY(${x * 4}deg)`
        }
      })
    }

    const resetHero = () => resetTransform(heroLayer)
    const resetPreview = () => resetTransform(preview)
    const resetMagnetic = (event: Event) =>
      resetTransform(event.currentTarget as HTMLElement)

    if (finePointer) {
      document.addEventListener("pointermove", updateMotion, { passive: true })
      hero?.addEventListener("pointerleave", resetHero)
      preview?.addEventListener("pointerleave", resetPreview)
      magneticButtons.forEach((button) =>
        button.addEventListener("pointerleave", resetMagnetic)
      )
    }

    return () => {
      observer.disconnect()
      window.cancelAnimationFrame(frame)
      document.removeEventListener("pointermove", updateMotion)
      hero?.removeEventListener("pointerleave", resetHero)
      preview?.removeEventListener("pointerleave", resetPreview)
      magneticButtons.forEach((button) =>
        button.removeEventListener("pointerleave", resetMagnetic)
      )
      spotlightCards.forEach((card) => {
        card.style.removeProperty("--spotlight-x")
        card.style.removeProperty("--spotlight-y")
      })
      document.documentElement.classList.remove("landing-reveal-ready")
    }
  }, [])

  return null
}
