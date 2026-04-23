import type { NextConfig } from "next";

/** See `src/app/api/v1/[[...path]]/route.ts` — explicit proxy; avoids rewrites that can fail on large JSON. */
const nextConfig: NextConfig = {};

export default nextConfig;
