import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export async function POST(request: NextRequest) {
  try {
    const cookie = request.cookies.get("access_token");
    const accessToken = cookie?.value;

    if (!accessToken) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
    }

    const body = await request.json();

    const backendResponse = await fetch(`${BACKEND_URL}/api/v1/fyers/connect`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      return NextResponse.json(data, { status: backendResponse.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("Fyers connect proxy error:", error);
    return NextResponse.json({ detail: "Failed to connect Fyers" }, { status: 500 });
  }
}