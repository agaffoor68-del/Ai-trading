import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export async function GET(request: NextRequest) {
  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;

    const searchParams = request.nextUrl.searchParams;
    const endpoint = `/api/v1/fyers/status${request.nextUrl.search}`;

    const backendResponse = await fetch(`${BACKEND_URL}${endpoint}`, {
      headers: {
        "Authorization": `Bearer ${accessToken}`,
      },
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      return NextResponse.json(data, { status: backendResponse.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("Fyers status proxy error:", error);
    return NextResponse.json({ detail: "Failed to get Fyers status" }, { status: 500 });
  }
}