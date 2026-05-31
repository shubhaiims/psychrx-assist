const DEFAULT_URL = "http://localhost:3000";

export function getSiteUrl(): URL {
  const explicit = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (explicit) {
    return new URL(explicit);
  }

  const production = process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  if (production) {
    return new URL(`https://${production}`);
  }

  const deployment = process.env.VERCEL_URL?.trim();
  if (deployment) {
    return new URL(`https://${deployment}`);
  }

  return new URL(DEFAULT_URL);
}
