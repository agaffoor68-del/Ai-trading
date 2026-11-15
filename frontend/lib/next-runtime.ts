const DYNAMIC_SERVER_USAGE_DIGEST = "DYNAMIC_SERVER_USAGE";

export function rethrowIfDynamicServerError(error: unknown): void {
  if (
    typeof error === "object" &&
    error !== null &&
    (error as { digest?: unknown }).digest === DYNAMIC_SERVER_USAGE_DIGEST
  ) {
    throw error;
  }
}