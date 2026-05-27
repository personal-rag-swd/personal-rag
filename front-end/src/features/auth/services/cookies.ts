import { cookies } from "next/headers";
import type { ResponseCookie } from "next/dist/compiled/@edge-runtime/cookies";
import type { NextResponse } from "next/server";

export const ACCESS_TOKEN_COOKIE = "access_token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

const isProduction = process.env.NODE_ENV === "production";

const accessTokenMaxAge = Number(process.env.ACCESS_TOKEN_MAX_AGE_SECONDS ?? 60 * 30);
const refreshTokenMaxAge = Number(process.env.REFRESH_TOKEN_MAX_AGE_SECONDS ?? 60 * 60 * 24 * 30);

const baseCookieOptions = {
  httpOnly: true,
  sameSite: "lax",
  secure: isProduction,
  path: "/",
} satisfies Partial<ResponseCookie>;

export const accessTokenCookieOptions = {
  ...baseCookieOptions,
  maxAge: accessTokenMaxAge,
} satisfies Partial<ResponseCookie>;

export const refreshTokenCookieOptions = {
  ...baseCookieOptions,
  maxAge: refreshTokenMaxAge,
} satisfies Partial<ResponseCookie>;

export async function setAuthCookies(tokens: {
  access_token: string;
  refresh_token: string;
}) {
  const cookieStore = await cookies();

  cookieStore.set(ACCESS_TOKEN_COOKIE, tokens.access_token, accessTokenCookieOptions);
  cookieStore.set(REFRESH_TOKEN_COOKIE, tokens.refresh_token, refreshTokenCookieOptions);
}

export async function clearAuthCookies() {
  const cookieStore = await cookies();

  cookieStore.delete(ACCESS_TOKEN_COOKIE);
  cookieStore.delete(REFRESH_TOKEN_COOKIE);
}

export function setAuthCookiesOnResponse(
  response: NextResponse,
  tokens: { access_token: string; refresh_token: string }
) {
  response.cookies.set(ACCESS_TOKEN_COOKIE, tokens.access_token, accessTokenCookieOptions);
  response.cookies.set(REFRESH_TOKEN_COOKIE, tokens.refresh_token, refreshTokenCookieOptions);
}

export function clearAuthCookiesOnResponse(response: NextResponse) {
  response.cookies.set(ACCESS_TOKEN_COOKIE, "", { ...baseCookieOptions, maxAge: 0 });
  response.cookies.set(REFRESH_TOKEN_COOKIE, "", { ...baseCookieOptions, maxAge: 0 });
}
