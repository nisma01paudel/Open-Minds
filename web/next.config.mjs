/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",        // a static bundle: no server needed on stage
  images: { unoptimized: true },
};
export default nextConfig;
