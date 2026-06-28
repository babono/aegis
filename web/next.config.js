/** @type {import('next').NextConfig} */
// In development the browser calls relative /api/* and Next proxies it to the
// FastAPI backend (default http://localhost:8000). In production we instead set
// NEXT_PUBLIC_API_BASE to the deployed backend URL and call it directly, so no
// rewrite is needed.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    if (process.env.NEXT_PUBLIC_API_BASE) return []; // prod: call backend directly
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` }];
  },
};

module.exports = nextConfig;
