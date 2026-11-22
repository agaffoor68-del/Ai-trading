import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL?.trim();

export const dynamic = "force-dynamic";

async function proxyRequest(request: NextRequest, endpoint: string) {
  if (!BACKEND_URL) {
    return NextResponse.json(
      { detail: "NEXT_PUBLIC_API_URL is not configured for this deployment." },
      { status: 503 },
    );
  }

  let backendOrigin: URL;
  try {
    backendOrigin = new URL(BACKEND_URL);
  } catch {
    return NextResponse.json(
      { detail: "NEXT_PUBLIC_API_URL must be a valid absolute HTTP(S) backend URL." },
      { status: 503 },
    );
  }
  if (!["http:", "https:"].includes(backendOrigin.protocol) || backendOrigin.pathname !== "/" || backendOrigin.search || backendOrigin.hash) {
    return NextResponse.json(
      { detail: "NEXT_PUBLIC_API_URL must contain only the backend origin." },
      { status: 503 },
    );
  }

  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;
    const incomingUrl = new URL(request.url);
    const searchParams = new URLSearchParams(incomingUrl.searchParams);
    searchParams.delete("nxtPslug");
    const queryString = searchParams.toString();

    const backendUrl = `${BACKEND_URL}${endpoint}${queryString ? `?${queryString}` : ""}`;
    const init: RequestInit = {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken && { "Authorization": `Bearer ${accessToken}` }),
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
    console.error(`Proxy error for ${endpoint}: ${error instanceof Error ? error.message : "unknown error"}`);
    return NextResponse.json({ detail: "Request failed" }, { status: 500 });
  }
}

export async function GET(request: NextRequest, { params }: { params: { slug: string[] } }) {
  const endpoint = `/api/v1/market/${params.slug.join("/")}`;
  return proxyRequest(request, endpoint);
}

export async function POST(request: NextRequest, { params }: { params: { slug: string[] } }) {
  const endpoint = `/api/v1/market/${params.slug.join("/")}`;
  return proxyRequest(request, endpoint);
}
