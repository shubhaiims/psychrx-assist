import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl();
  const host = siteUrl.toString().replace(/\/$/, "");

  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/admin/rules"],
    },
    sitemap: `${host}/sitemap.xml`,
    host,
  };
}
