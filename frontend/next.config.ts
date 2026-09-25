import type { NextConfig } from "next";

if (process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_URL) {
  throw new Error("NEXT_PUBLIC_API_URL must be configured for a production build.");
}

const nextConfig: NextConfig = { agentRules: false };

export default nextConfig;
