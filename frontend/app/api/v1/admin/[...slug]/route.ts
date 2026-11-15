import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

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
    console.error(`Admin proxy error for ${endpoint}:`, error);
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