import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (accessToken) { headers["Authorization"] = "Bearer " + accessToken; }
    const queryString = new URL(request.url).search;
    const backendResponse = await fetch(BACKEND_URL + "/api/v1/indicators" + queryString, {
      method: "GET", headers, cache: "no-store",
    });
    const data = await backendResponse.json();
    if (!backendResponse.ok) { return NextResponse.json(data, { status: backendResponse.status }); }
    return NextResponse.json(data);
  } catch (error) {
    rethrowIfDynamicServerError(error);
    console.error("Indicators proxy error: " + (error instanceof Error ? error.message : "unknown"));
    return NextResponse.json({ detail: "Failed to fetch indicators" }, { status: 500 });
  }
}
