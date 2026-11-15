import { NextRequest, NextResponse } from "next/server";
import { rethrowIfDynamicServerError } from "@/lib/next-runtime";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export const dynamic = "force-dynamic";

async function proxy(request: NextRequest, path: string[]) {
  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;

    const search = request.nextUrl.search;
    const init: RequestInit = {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
      },
      cache: "no-store",
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      const body = await request.text();
      if (body) {
        init.body = body;
      }
    }

    const backendResponse = await fetch(`${BACKEND_URL}/api/${path.join("/")}${search}`, init);
    const text = await backendResponse.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: `Backend returned a non-JSON response (status ${backendResponse.status}).` };
      }
    }

    if (!backendResponse.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? (data as { detail: unknown }).detail
          : `Backend error (status ${backendResponse.status}).`;
      return NextResponse.json({ detail }, { status: backendResponse.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    rethrowIfDynamicServerError(error);
    console.error(`Proxy error for /api/${path.join("/")}: ${error instanceof Error ? error.message : "unknown error"}`);
    return NextResponse.json({ detail: "Request failed" }, { status: 502 });
  }
}

export async function GET(request: NextRequest, { params }: { params: { slug: string[] } }) {
  return proxy(request, params.slug);
}

export async function POST(request: NextRequest, { params }: { params: { slug: string[] } }) {
  return proxy(request, params.slug);
}

export async function PUT(request: NextRequest, { params }: { params: { slug: string[] } }) {
  return proxy(request, params.slug);
}

export async function PATCH(request: NextRequest, { params }: { params: { slug: string[] } }) {
  return proxy(request, params.slug);
}

export async function DELETE(request: NextRequest, { params }: { params: { slug: string[] } }) {
  return proxy(request, params.slug);
}