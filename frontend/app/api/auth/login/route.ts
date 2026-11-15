import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const email = formData.get("username") as string;
    const password = formData.get("password") as string;

    if (!email || !password) {
      return NextResponse.json(
        { detail: "Email and password required" },
        { status: 400 }
      );
    }

    const backendResponse = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        username: email,
        password: password,
      }),
    });

    const data = await backendResponse.json();

    if (!backendResponse.ok) {
      const errorResponse = NextResponse.json(data, { status: backendResponse.status });
      
      // Forward the access_token cookie if present
      const setCookie = backendResponse.headers.get("set-cookie");
      if (setCookie) {
        // Extract cookie options and set on our domain
        errorResponse.headers.set("set-cookie", setCookie.replace("SameSite=Lax", "SameSite=Lax"));
      }
      
      return errorResponse;
    }

    const response = NextResponse.json(data);
    
    // Set httpOnly cookie
    const setCookie = backendResponse.headers.get("set-cookie");
    if (setCookie) {
      response.headers.set("set-cookie", setCookie);
    }

    return response;
  } catch (error) {
    console.error("Login proxy error:", error);
    return NextResponse.json(
      { detail: "Login failed. Please try again." },
      { status: 500 }
    );
  }
}