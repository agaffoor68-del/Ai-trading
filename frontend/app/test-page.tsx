"use client";
import { useState, useEffect } from "react";
export default function TestPage() {
  const [x, setX] = useState(0);
  useEffect(() => { setX(1); }, []);
  return <div>Test {x}</div>;
}
