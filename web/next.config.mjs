/** @type {import('next').NextConfig} */
// GitHub Pages serves a project repository from /<repo>/, not from the root, so every asset and
// every data fetch has to be prefixed. It is an env var rather than a constant because the app must
// still build and run at the root locally - a hardcoded /work would break `npm run dev`.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  basePath,
  assetPrefix: basePath || undefined,
};
export default nextConfig;
