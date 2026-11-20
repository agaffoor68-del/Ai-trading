"use client";

import { useEffect } from "react";

export default function AdminError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Admin route render error:", error);
  }, [error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-true-black px-6 text-center text-white">
      <section className="max-w-md" role="alert">
        <h1 className="text-xl font-semibold">Admin page couldn&apos;t load</h1>
        <p className="mt-2 text-sm text-text-secondary">A temporary display error occurred. Try loading the page again.</p>
        <button
          type="button"
          onClick={reset}
          className="mt-5 rounded-lg bg-neon-cyan px-4 py-2 font-semibold text-true-black hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon-cyan"
        >
          Try again
        </button>
      </section>
    </main>
  );
}
