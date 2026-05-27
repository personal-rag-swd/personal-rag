import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { useAuthStore } from "@/features/auth/store/auth-store";

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let refreshTokenPromise: Promise<void> | null = null;

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/",
  withCredentials: true,
});

const refreshClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/",
  withCredentials: true,
});

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

apiClient.interceptors.request.use((config) => {
  config.withCredentials = true;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableRequestConfig | undefined;

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      isAuthRotationRequest(originalRequest)
    ) {
      return Promise.reject(toApiError(error));
    }

    if (originalRequest._retry) {
      useAuthStore.getState().clearSession();
      return Promise.reject(toApiError(error));
    }

    originalRequest._retry = true;

    try {
      await refreshAccessToken();
      return apiClient.request(originalRequest);
    } catch {
      useAuthStore.getState().clearSession();
      return Promise.reject(new ApiError("Session expired. Please log in again.", 401));
    }
  }
);

export async function refreshAccessToken(): Promise<void> {
  refreshTokenPromise ??= refreshClient
    .post("/api/v1/auth/token-refreshes")
    .then(() => undefined)
    .finally(() => {
      refreshTokenPromise = null;
    });

  return refreshTokenPromise;
}

export async function apiFetch<TData = unknown>(
  path: string,
  options: AxiosRequestConfig = {}
): Promise<TData> {
  const response = await apiClient.request<TData>({
    url: path,
    ...options,
  });

  return response.data;
}

function isAuthRotationRequest(config: InternalAxiosRequestConfig) {
  const url = config.url ?? "";

  return url.includes("/auth/sessions") || url.includes("/auth/token-refreshes");
}

function toApiError(error: AxiosError) {
  return new ApiError(parseAxiosError(error), error.response?.status ?? 500);
}

function parseAxiosError(error: AxiosError) {
  const detail = getDetail(error.response?.data);
  if (detail) {
    return detail;
  }

  return error.response?.statusText || error.message || "The request could not be completed.";
}

function getDetail(data: unknown) {
  if (!data || typeof data !== "object" || !("detail" in data)) {
    return null;
  }

  const detail = (data as { detail: unknown }).detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((entry) => {
        if (entry && typeof entry === "object" && "msg" in entry) {
          const message = (entry as { msg: unknown }).msg;
          return typeof message === "string" ? message : null;
        }

        return null;
      })
      .filter(Boolean)
      .join(" ");
  }

  return null;
}
