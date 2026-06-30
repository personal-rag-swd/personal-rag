import { create } from "zustand"

import { apiClient, apiFetch } from "@/lib/api-client"

interface User {
  id: string
  email: string
  role: string
  is_active: boolean
}

interface AuthStore {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  clearSession: () => void
  setIsLoading: (isLoading: boolean) => void
  initializeSession: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  startRegistration: (
    email: string,
    password: string
  ) => Promise<{ step: "otp" | "details" }>
  verifyRegistration: (email: string, otp: string) => Promise<void>
  requestPasswordReset: (email: string) => Promise<void>
  completePasswordReset: (
    email: string,
    otp: string,
    newPassword: string
  ) => Promise<void>
  logout: () => Promise<void>
}

async function fetchCurrentUser() {
  return apiFetch<User>("/api/v1/users/me")
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  clearSession: () => {
    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    })
  },
  setIsLoading: (isLoading) => set({ isLoading }),
  initializeSession: async () => {
    set({ isLoading: true })

    try {
      const user = await fetchCurrentUser()
      set({
        user,
        isAuthenticated: true,
      })
    } catch {
      get().clearSession()
    } finally {
      set({ isLoading: false })
    }
  },
  login: async (email, password) => {
    const body = new URLSearchParams({
      username: email,
      password,
    })

    await apiClient.post("/api/v1/auth/sessions", body, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    })

    try {
      const user = await fetchCurrentUser()
      set({
        user,
        isAuthenticated: true,
      })
    } catch (error) {
      get().clearSession()
      throw error
    }
  },
  startRegistration: async (email, password) => {
    await apiClient.post("/api/v1/auth/registrations", {
      email,
      password,
    })

    return { step: "otp" as const }
  },
  verifyRegistration: async (email, otp) => {
    await apiClient.post("/api/v1/auth/email-verifications", {
      email,
      otp,
    })
  },
  requestPasswordReset: async (email) => {
    await apiClient.post("/api/v1/auth/password-resets", { email })
  },
  completePasswordReset: async (email, otp, newPassword) => {
    await apiClient.post("/api/v1/auth/password-resets/verify", {
      email,
      otp,
      new_password: newPassword,
    })
  },
  logout: async () => {
    try {
      await apiFetch<void>("/api/v1/auth/sessions/current", {
        method: "DELETE",
      })
    } catch {
      // The client still clears its session even if the server-side logout fails.
    }

    get().clearSession()
  },
}))

export function useAuth() {
  return useAuthStore()
}
