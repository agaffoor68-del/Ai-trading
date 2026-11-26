import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export const dynamic = "force-dynamic";

async function proxyRequest(request: NextRequest, endpoint: string) {
  if (!BACKEND_URL) {
    return NextResponse.json({ detail: "NEXT_PUBLIC_API_URL is not configured." }, { status: 503 });
  }
  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (accessToken) { headers["Authorization"] = "Bearer " + accessToken; }
    const init: RequestInit = { method: request.method, headers, cache: "no-store" };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = JSON.stringify(await request.json());
    }
    const backendResponse = await fetch(BACKEND_URL + endpoint, init);
    const data = await backendResponse.json();
    if (!backendResponse.ok) { return NextResponse.json(data, { status: backendResponse.status }); }
    return NextResponse.json(data);
  } catch (error) {
    rethrowIfDynamicServerError(error);
    console.error("Strategies proxy error: " + (error instanceof Error ? error.message : "unknown"));
    return NextResponse.json({ detail: "Request failed" }, { status: 500 });
  }
}

export async function GET(request: NextRequest) { return proxyRequest(request, "/api/v1/strategies"); }
export async function POST(request: NextRequest) { return proxyRequest(request, "/api/v1/strategies"); }
export async function PUT(request: NextRequest) { return proxyRequest(request, "/api/v1/strategies"); }
export async function DELETE(request: NextRequest) { return proxyRequest(request, "/api/v1/strategies"); }
