"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getApiBaseUrl, parseApiError } from "@/features/auth/services/api";
import {
  clearAuthCookies,
  REFRESH_TOKEN_COOKIE,
  setAuthCookies,
} from "@/features/auth/services/cookies";
import {
  loginSchema,
  registrationSchema,
  verificationSchema,
  type AuthActionState,
  type TokenPair,
} from "@/features/auth/types";

function formDataToObject(formData: FormData) {
  return Object.fromEntries(formData.entries());
}

function getFieldErrors(
  error: { flatten: () => { fieldErrors: Record<string, string[] | undefined> } }
): AuthActionState["fieldErrors"] {
  const { fieldErrors } = error.flatten();

  return {
    email: fieldErrors.email?.[0],
    password: fieldErrors.password?.[0],
    otp: fieldErrors.otp?.[0],
  };
}

export async function loginAction(
  _prevState: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const parsed = loginSchema.safeParse(formDataToObject(formData));
  if (!parsed.success) {
    return {
      email: typeof formData.get("email") === "string" ? String(formData.get("email")) : "",
      formError: "Invalid format",
      fieldErrors: getFieldErrors(parsed.error),
    };
  }
  const { email, password } = parsed.data;

  const body = new URLSearchParams({
    username: email,
    password,
  });

  let tokens: TokenPair;
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/sessions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        email,
        formError:
          response.status === 401
            ? "Incorrect email or password."
            : await parseApiError(response),
      };
    }

    tokens = (await response.json()) as TokenPair;
  } catch {
    return {
      email,
      formError: "Could not reach the API. Check API_BASE_URL and try again.",
    };
  }

  await setAuthCookies(tokens);
  redirect("/dashboard");
}

export async function startRegistrationAction(
  _prevState: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const parsed = registrationSchema.safeParse(formDataToObject(formData));
  if (!parsed.success) {
    return {
      step: "details",
      email: typeof formData.get("email") === "string" ? String(formData.get("email")) : "",
      formError: "Invalid format",
      fieldErrors: getFieldErrors(parsed.error),
    };
  }
  const { email, password } = parsed.data;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/registrations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        step: "details",
        email,
        formError: await parseApiError(response),
      };
    }
  } catch {
    return {
      step: "details",
      email,
      formError: "Could not reach the API. Check API_BASE_URL and try again.",
    };
  }

  return { step: "otp", email };
}

export async function verifyRegistrationAction(
  _prevState: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const parsed = verificationSchema.safeParse(formDataToObject(formData));
  if (!parsed.success) {
    return {
      step: "otp",
      email: typeof formData.get("email") === "string" ? String(formData.get("email")) : "",
      formError: "Invalid format",
      fieldErrors: getFieldErrors(parsed.error),
    };
  }
  const { email, otp } = parsed.data;

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/email-verifications`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, otp }),
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        step: "otp",
        email,
        formError: await parseApiError(response),
      };
    }
  } catch {
    return {
      step: "otp",
      email,
      formError: "Could not reach the API. Check API_BASE_URL and try again.",
    };
  }

  redirect("/login");
}

export async function logoutAction() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (refreshToken) {
    try {
      await fetch(`${getApiBaseUrl()}/api/v1/auth/sessions/current`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
    } catch {
      // Local cookies still need to be cleared when the API is unavailable.
    }
  }

  await clearAuthCookies();
  redirect("/login");
}
