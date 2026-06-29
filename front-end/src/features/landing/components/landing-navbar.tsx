import { useEffect, useRef, useState } from "react"
import { ArrowRightIcon, MenuIcon, XIcon } from "lucide-react"
import { createPortal } from "react-dom"
import { Link } from "react-router-dom"

import { AviaryLogo } from "@/components/branding/aviary-logo"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const navigation = [
  { label: "Workspace", href: "#workspace" },
  { label: "How it Works", href: "#workflow" },
  { label: "Features", href: "#features" },
  { label: "Studio", href: "#studio" },
]

export function LandingNavbar() {
  const [isScrolled, setIsScrolled] = useState(false)
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [activeSection, setActiveSection] = useState("")
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const update = () => setIsScrolled(window.scrollY > 24)
    update()
    window.addEventListener("scroll", update, { passive: true })
    return () => window.removeEventListener("scroll", update)
  }, [])

  useEffect(() => {
    const sections = navigation
      .map((item) => document.querySelector<HTMLElement>(item.href))
      .filter((section): section is HTMLElement => section !== null)

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleSection = entries.find((entry) => entry.isIntersecting)
        if (visibleSection) setActiveSection(`#${visibleSection.target.id}`)
      },
      { rootMargin: "-18% 0px -68%", threshold: 0 }
    )

    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!isMenuOpen) return

    const previousOverflow = document.body.style.overflow
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMenuOpen(false)
        menuButtonRef.current?.focus()
        return
      }

      if (event.key !== "Tab") return
      const dialog = document.querySelector<HTMLElement>("#mobile-navigation")
      const focusable = dialog?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
      if (!focusable?.length) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    const handleResize = () => {
      if (window.innerWidth >= 768) setIsMenuOpen(false)
    }

    document.body.style.overflow = "hidden"
    window.addEventListener("keydown", handleKeyDown)
    window.addEventListener("resize", handleResize)
    closeButtonRef.current?.focus()

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener("keydown", handleKeyDown)
      window.removeEventListener("resize", handleResize)
    }
  }, [isMenuOpen])

  const closeMenu = () => setIsMenuOpen(false)

  return (
    <header
      className={cn(
        "sticky top-0 z-50 border-b transition-[background-color,border-color,box-shadow,backdrop-filter] duration-500",
        isScrolled
          ? "border-white/10 bg-background/90 shadow-lg shadow-black/10 backdrop-blur-2xl"
          : "border-white/5 bg-background/70 backdrop-blur-lg"
      )}
    >
      <nav
        aria-label="Primary navigation"
        className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8"
      >
        <Link
          to="/"
          className="flex items-center gap-2.5"
          aria-label="Aviary home"
        >
          <AviaryLogo className="size-9 object-contain" />
          <span className="text-sm font-semibold tracking-tight">Aviary</span>
        </Link>

        <div className="hidden items-center gap-7 md:flex">
          {navigation.map((item) => (
            <a
              key={item.href}
              href={item.href}
              data-active={activeSection === item.href}
              aria-current={
                activeSection === item.href ? "location" : undefined
              }
              className={cn(
                "landing-nav-link text-sm transition-colors duration-300 hover:text-foreground",
                activeSection === item.href
                  ? "text-foreground"
                  : "text-muted-foreground"
              )}
            >
              {item.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            nativeButton={false}
            render={<Link to="/login" />}
          >
            Sign In
          </Button>
          <Button
            className="hidden shadow-lg shadow-primary/20 sm:inline-flex"
            nativeButton={false}
            render={<Link to="/register" />}
          >
            Get Started
            <ArrowRightIcon
              data-icon="inline-end"
              className="transition-transform duration-300 group-hover/button:translate-x-0.5"
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open navigation menu"
            aria-expanded={isMenuOpen}
            aria-controls="mobile-navigation"
            onClick={() => setIsMenuOpen(true)}
            ref={menuButtonRef}
          >
            <MenuIcon />
          </Button>
        </div>
      </nav>

      {isMenuOpen
        ? createPortal(
            <div className="fixed inset-x-0 top-16 bottom-0 z-50 md:hidden">
              <button
                type="button"
                className="absolute inset-0 bg-black/70"
                aria-label="Close navigation menu"
                onClick={closeMenu}
              />
              <div
                id="mobile-navigation"
                role="dialog"
                aria-modal="true"
                aria-label="Navigation menu"
                className="absolute top-0 right-0 h-full w-[min(22rem,88vw)] border-l border-white/10 bg-background p-5 shadow-2xl shadow-black/40"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">Explore Aviary</span>
                  <Button
                    ref={closeButtonRef}
                    variant="ghost"
                    size="icon"
                    aria-label="Close navigation menu"
                    onClick={closeMenu}
                  >
                    <XIcon />
                  </Button>
                </div>
                <div className="mt-6 flex flex-col gap-1">
                  {navigation.map((item, index) => (
                    <a
                      key={item.href}
                      href={item.href}
                      aria-current={
                        activeSection === item.href ? "location" : undefined
                      }
                      onClick={closeMenu}
                      className={cn(
                        "flex items-center justify-between rounded-xl px-4 py-3.5 text-sm transition-colors",
                        activeSection === item.href
                          ? "bg-primary/15 text-white"
                          : "text-muted-foreground hover:bg-white/5 hover:text-white"
                      )}
                    >
                      <span>{item.label}</span>
                      <span className="text-xs text-white/30 tabular-nums">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    </a>
                  ))}
                </div>
                <div className="mt-6 grid gap-2 border-t border-white/10 pt-6">
                  <Button nativeButton={false} render={<Link to="/register" />}>
                    Get Started
                    <ArrowRightIcon data-icon="inline-end" />
                  </Button>
                  <Button
                    variant="outline"
                    nativeButton={false}
                    render={<Link to="/login" />}
                  >
                    Sign In
                  </Button>
                </div>
              </div>
            </div>,
            document.body
          )
        : null}
    </header>
  )
}
