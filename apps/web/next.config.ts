import type { NextConfig } from "next";

/** Fail fast on Vercel when public env vars are missing. */
const REQUIRED_PUBLIC_ENV = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "NEXT_PUBLIC_API_URL",
] as const;

function assertProductionEnv(): void {
  if (process.env.VERCEL !== "1") {
    return;
  }
  const missing = REQUIRED_PUBLIC_ENV.filter((key) => !process.env[key]?.trim());
  if (missing.length > 0) {
    throw new Error(
      `Missing Vercel environment variables: ${missing.join(", ")}. ` +
        "Set them in Project Settings → Environment Variables (see DEPLOY.md).",
    );
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim() ?? "";
  if (!/^https?:\/\//.test(apiUrl)) {
    throw new Error(
      `Invalid NEXT_PUBLIC_API_URL: "${apiUrl}". ` +
        "Must be an absolute URL starting with http:// or https:// (see DEPLOY.md).",
    );
  }
}

assertProductionEnv();

const nextConfig: NextConfig = {};

export default nextConfig;
