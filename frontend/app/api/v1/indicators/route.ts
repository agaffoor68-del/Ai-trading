import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, method: "GET" | "POST") {
  try {
    const cookie = request.cookies.get("access_token");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (cookie?.value) headers["Authorization"] = `Bearer ${cookie.value}`;
    const init: RequestInit = { method, headers, cache: "no-store" };
    if (method === "POST") init.body = await request.text();
    const backendResponse = await fetch(BACKEND_URL + "/api/v1/indicators" + new URL(request.url).search, init);
    const data = await backendResponse.json().catch(() => ({ detail: "Invalid backend response" }));
    return NextResponse.json(data, { status: backendResponse.status });
  } catch (error) {
    rethrowIfDynamicServerError(error);
    console.error("Indicators proxy error: " + (error instanceof Error ? error.message : "unknown"));
    return NextResponse.json({ detail: "Failed to reach the indicator service" }, { status: 502 });
  }
}

export async function GET(request: NextRequest) {
  return proxy(request, "GET");
}

export async function POST(request: NextRequest) {
  return proxy(request, "POST");
}
