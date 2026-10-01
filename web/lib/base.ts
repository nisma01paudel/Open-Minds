/**
 * The deployment prefix, from NEXT_PUBLIC_BASE_PATH, empty when running locally.
 *
 * `basePath` in next.config handles <Link> and static assets automatically, but it does NOT rewrite
 * raw fetch() calls - those are strings this app builds itself. So every /data request goes through
 * here.
 *
 * Deliberately NOT applied to /api/v1/... calls: those address the field API, which is a separate
 * service that is not deployed with the pages and must keep its own host.
 */
export const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";

/** A path under the deployed root, e.g. dataUrl("/data/x.json") -> "/work/data/x.json". */
export const dataUrl = (path: string): string => `${BASE}${path}`;
