import { errors, jwtVerify } from "jose";
import { NextResponse, type NextRequest } from "next/server";

import { getApiBaseUrl } from "@/features/auth/services/api";
import {
  ACCESS_TOKEN_COOKIE,
  clearAuthCookiesOnResponse,
  REFRESH_TOKEN_COOKIE,
  setAuthCookiesOnResponse,
} from "@/features/auth/services/cookies";
import { type TokenPair } from "@/features/auth/types";

const secret = new TextEncoder().encode(process.env.JWT_SECRET_KEY ?? "change-me");
const algorithm = process.env.JWT_ALGORITHM ?? "HS256";

const PUBLIC_PATHS = ["/login", "/register"];

function redirectToLogin(request: NextRequest) {
  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";

  const response = NextResponse.redirect(url);
  clearAuthCookiesOnResponse(response);
  return response;
}

async function verifyAccessToken(accessToken: string) {
  await jwtVerify(accessToken, secret, {
    algorithms: [algorithm],
  });
}

async function rotateTokens(refreshToken: string) {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/token-refreshes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as TokenPair;
}

export async function authMiddleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isPublicPath = PUBLIC_PATHS.includes(pathname);

  const accessToken = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_TOKEN_COOKIE)?.value;

  if (isPublicPath) {
    // If the user has a session, redirect from public pages (/login, /register) to /dashboard
    if (refreshToken) {
      if (accessToken) {
        try {
          await verifyAccessToken(accessToken);
          const url = request.nextUrl.clone();
          url.pathname = "/dashboard";
          return NextResponse.redirect(url);
        } catch {
          // Access token expired, proceed to attempt refresh token rotation
        }
      }

      const tokens = await rotateTokens(refreshToken);
      if (tokens) {
        const url = request.nextUrl.clone();
        url.pathname = "/dashboard";
        const response = NextResponse.redirect(url);
        setAuthCookiesOnResponse(response, tokens);
        return response;
      }
    }
    return NextResponse.next();
  }

  // Protected paths flow
  if (!refreshToken) {
    return redirectToLogin(request);
  }

  if (accessToken) {
    try {
      await verifyAccessToken(accessToken);
      return NextResponse.next();
    } catch (error) {
      if (!(error instanceof errors.JWTExpired)) {
        return redirectToLogin(request);
      }
    }
  }

  const tokens = await rotateTokens(refreshToken);
  if (!tokens) {
    return redirectToLogin(request);
  }

  const response = NextResponse.next();
  setAuthCookiesOnResponse(response, tokens);
  return response;
}
