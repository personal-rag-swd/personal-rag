import { create } from "zustand";

import {
  apiClient,
  apiFetch,
  refreshAccessToken,
} from "@/lib/api-client";

interface User {
  email: string;
}

interface LoginResponse {
  access_token: string;
}

interface JwtPayload {
  email?: string;
  sub?: string;
}

interface AuthStore {
  accessToken: string | null;
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  setAccessToken: (token: string | null) => void;
  setIsLoading: (isLoading: boolean) => void;
  initializeSession: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  startRegistration: (email: string, password: string) => Promise<{ step: "otp" | "details" }>;
  verifyRegistration: (email: string, otp: string) => Promise<void>;
  logout: () => Promise<void>;
}

function decodeJwt(token: string): JwtPayload | null {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      window
        .atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

function getUserFromToken(token: string | null): User | null {
  if (!token) {
    return null;
  }

  const decoded = decodeJwt(token);
  const email = decoded?.sub || decoded?.email || "workspace@example.com";

  return { email };
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  accessToken: null,
  isAuthenticated: false,
  user: null,
  isLoading: true,
  setAccessToken: (token) => {
    set({
      accessToken: token,
      isAuthenticated: Boolean(token),
      user: getUserFromToken(token),
    });
  },
  setIsLoading: (isLoading) => set({ isLoading }),
  initializeSession: async () => {
    set({ isLoading: true });

    try {
      await refreshAccessToken();
    } catch {
      get().setAccessToken(null);
    } finally {
      set({ isLoading: false });
    }
  },
  login: async (email, password) => {
    const body = new URLSearchParams({
      username: email,
      password,
    });

    const response = await apiClient.post<LoginResponse>("/api/v1/auth/sessions", body, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });

    get().setAccessToken(response.data.access_token);
  },
  startRegistration: async (email, password) => {
    await apiClient.post("/api/v1/auth/registrations", {
      email,
      password,
    });

    return { step: "otp" as const };
  },
  verifyRegistration: async (email, otp) => {
    await apiClient.post("/api/v1/auth/email-verifications", {
      email,
      otp,
    });
  },
  logout: async () => {
    try {
      await apiFetch<void>("/api/v1/auth/sessions/current", {
        method: "DELETE",
      });
    } catch {
      // Fallback: still perform client logout even if deletion fails on the server.
    }

    get().setAccessToken(null);
  },
}));

export function useAuth() {
  return useAuthStore();
}
