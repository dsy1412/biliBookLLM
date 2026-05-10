import path from "path";
import type { NextConfig } from "next";

/** See `src/app/api/v1/[[...path]]/route.ts`: explicit proxy; avoids rewrites that can fail on large JSON. */
const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
