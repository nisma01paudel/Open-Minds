/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: no server needed on stage. trailingSlash makes /ar/ resolve to
  // ar/index.html, so the app also works behind a plain file server - without it the
  // route exports as ar.html and /ar/ 404s.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};
export default nextConfig;
