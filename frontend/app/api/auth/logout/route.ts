import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ message: "Logged out successfully" });
  
  // Clear the access_token cookie
  response.cookies.delete("access_token");
  
  return response;
}