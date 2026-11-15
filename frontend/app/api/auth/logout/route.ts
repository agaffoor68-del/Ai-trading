import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST() {
  const response = NextResponse.json({ message: "Logged out successfully" });

  response.cookies.set({
    name: "access_token",
    value: "",
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  return response;
}