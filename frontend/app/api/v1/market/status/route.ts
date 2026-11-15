import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;

    const endpoint = `/api/v1/market/status${request.nextUrl.search}`;

    const backendResponse = await fetch(`${BACKEND_URL}${endpoint}`, {
      headers: {
        "Authorization": `Bearer ${accessToken}`,
      },
      cache: "no-store",
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      return NextResponse.json(data, { status: backendResponse.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    rethrowIfDynamicServerError(error);
    console.error(`Market status proxy error: ${error instanceof Error ? error.message : "unknown error"}`);
    return NextResponse.json({ detail: "Failed to get market status" }, { status: 500 });
  }
}