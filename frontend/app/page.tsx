"use client";

import { useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/')
      .then((res) => res.json())
      .then((data) => setStatus(JSON.stringify(data, null, 2)))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <main className="min-h-screen bg-slate-50 p-8 font-sans text-slate-900">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-4">Options Trading Platform</h1>
        <p className="mb-6 text-slate-600">Frontend connected to backend at {API_URL}</p>
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded text-red-800 text-sm">
            Error connecting to backend: {error}
          </div>
        )}
        <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-3">Backend API Status (GET /api/)</h2>
          <pre className="bg-slate-100 p-4 rounded text-sm overflow-x-auto">{status || 'Loading...'}</pre>
        </div>
        <div className="mt-6 flex gap-3">
          <a href="/api/health" className="inline-block px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Health Check</a>
          <a href="/api/docs" className="inline-block px-4 py-2 bg-slate-800 text-white rounded text-sm hover:bg-slate-900">API Docs</a>
        </div>
      </div>
    </main>
  );
}
