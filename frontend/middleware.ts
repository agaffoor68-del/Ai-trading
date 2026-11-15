import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

// Paths that don't require authentication
const PUBLIC_PATHS = ["/login"];

// Paths that require admin role
const ADMIN_PATHS = ["/admin", "/api/v1/admin"];

// JWT secret for verifying tokens (should match backend JWT_SECRET)
const JWT_SECRET = process.env.JWT_SECRET || "your-super-secret-jwt-key-change-in-production";

async function verifyToken(token: string) {
  try {
    const secret = new TextEncoder().encode(JWT_SECRET);
    const { payload } = await jwtVerify(token, secret);
    return payload;
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some(path => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Check for auth token in cookie
  const cookie = request.cookies.get("access_token");
  const token = cookie?.value;

  if (!token) {
    // No token - redirect to login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Verify token
  const payload = await verifyToken(token);
  if (!payload) {
    // Invalid token - clear cookie and redirect to login
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete("access_token");
    return response;
  }

  // Check admin routes
  if (ADMIN_PATHS.some(path => pathname.startsWith(path))) {
    const role = payload.role as string;
    if (role !== "ADMIN") {
      // Not admin - redirect to 403 page
      return NextResponse.redirect(new URL("/403", request.url));
    }
  }

  // Token is valid, continue
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)",
  ],
}