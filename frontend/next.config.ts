import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "www.camara.leg.br" },
      { protocol: "https", hostname: "**.camara.gov.br" },
    ],
  },
};

export default nextConfig;
