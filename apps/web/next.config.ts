import type { NextConfig } from "next";

// The browser always calls the API through this app's own origin
// (/api/v1/...), and Next.js proxies those requests to the FastAPI service.
// That keeps the weather_visitor cookie first-party on the web domain even
// though the API runs on Cloud Run under a different hostname.
const apiOrigin = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  poweredByHeader: false,
  transpilePackages: ["@weather/api-types"],
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "geolocation=(self), camera=(), microphone=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
