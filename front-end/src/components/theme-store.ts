import { create } from "zustand"
import { persist } from "zustand/middleware"

export type Theme = "dark" | "light" | "system"

type ThemeState = {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "dark",
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "vite-ui-theme",
    }
  )
)

export const useTheme = () => {
  return useThemeStore()
}
