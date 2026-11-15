import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export const dynamic = "force-dynamic";

async function proxyRequest(request: NextRequest, endpoint: string) {
  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;

    if (!accessToken) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
    }

    const backendUrl = `${BACKEND_URL}${endpoint}`;
    const init: RequestInit = {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${accessToken}`,
      },
      cache: "no-store",
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      const body = await request.json();
      init.body = JSON.stringify(body);
    }

    const backendResponse = await fetch(backendUrl, init);
    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      return NextResponse.json(data, { status: backendResponse.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    rethrowIfDynamicServerError(error);
    console.error(`Admin proxy error for ${endpoint}: ${error instanceof Error ? error.message : "unknown error"}`);
    return NextResponse.json({ detail: "Request failed" }, { status: 500 });
  }
}

export async function GET(request: NextRequest, { params }: { params: { slug: string[] } }) {
  const endpoint = `/api/v1/admin/${params.slug.join("/")}`;
  return proxyRequest(request, endpoint);
}

export async function POST(request: NextRequest, { params }: { params: { slug: string[] } }) {
  const endpoint = `/api/v1/admin/${params.slug.join("/")}`;
  return proxyRequest(request, endpoint);
}

export async function DELETE(request: NextRequest, { params }: { params: { slug: string[] } }) {
  const endpoint = `/api/v1/admin/${params.slug.join("/")}`;
  return proxyRequest(request, endpoint);
}