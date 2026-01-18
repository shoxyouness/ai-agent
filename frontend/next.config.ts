import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  webpack: (config) => {
    config.externals.push({
      "node:path": "commonjs path",
    });
    return config;
  },
};

export default nextConfig;
