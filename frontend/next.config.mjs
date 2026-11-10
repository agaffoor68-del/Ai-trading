/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // In production, API calls are proxied via Vercel's routing
    // In development, we rewrite to the local backend
    const destination = process.env.NEXT_PUBLIC_API_URL;

    if (!destination) {
      return [];
    }
    return [
      {
        source: '/api/:path*',
        destination: `${destination}/:path*`,
      },
    ];
  },
};

export default nextConfig;
