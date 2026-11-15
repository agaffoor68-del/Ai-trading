import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const email = formData.get("username") as string;
    const password = formData.get("password") as string;

    if (!email || !password) {
      return NextResponse.json(
        { detail: "Email and password required" },
        { status: 400 }
      );
    }

    const backendResponse = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        username: email,
        password: password,
      }),
      cache: "no-store",
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      return NextResponse.json(data, { status: backendResponse.status });
    }

    const { access_token: accessToken, expires_in: expiresIn, ...userData } = data;

    if (!accessToken) {
      return NextResponse.json(
        { detail: "Login failed: backend did not return a session token." },
        { status: 502 }
      );
    }

    const response = NextResponse.json(userData);

    response.cookies.set({
      name: "access_token",
      value: accessToken,
      httpOnly: true,
      secure: true,
      sameSite: "lax",
      path: "/",
      maxAge: typeof expiresIn === "number" ? expiresIn : 60 * 60 * 24,
    });

    return response;
  } catch (error) {
    rethrowIfDynamicServerError(error);

    const isNetworkError = error instanceof TypeError;
    const message = error instanceof Error ? error.message : "unknown error";
    console.error(`Login proxy error: ${message}`);

    return NextResponse.json(
      {
        detail: isNetworkError
          ? "Unable to reach the authentication server. Please try again later."
          : "Login failed due to a server error. Please try again.",
      },
      { status: isNetworkError ? 502 : 500 }
    );
  }
}