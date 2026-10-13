import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // In development, /api/py/* on the Next port reaches the local uvicorn (handy
  // for curl). In production vercel.json rewrites /api/py/* to the Python function.
  async rewrites() {
    return process.env.NODE_ENV === "development" && process.env.ENGINE_URL
      ? [{ source: "/api/py/:path*", destination: `${process.env.ENGINE_URL.replace(/\/+$/, "")}/api/py/:path*` }]
      : [];
  },
  // The Python compute function lives in the same Vercel project (api/index.py);
  // the browser never calls it directly — src/app/api/engine proxies with the key.
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
