import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import { getSiteUrl } from "@/lib/site";
import "./globals.css";

const siteUrl = getSiteUrl();

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: "PsychRx Assist - Structured Psychiatry Prescribing Assessments",
  description:
    "Clinician-facing psychiatry prescribing decision support with transparent rule logic, monitoring prompts, and guideline-linked explanations.",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "PsychRx Assist",
    description: "Structured psychiatry prescribing assessments for qualified clinicians.",
    url: siteUrl,
    siteName: "PsychRx Assist",
    locale: "en_US",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="appbar">
          <div className="appbarInner">
            <div className="brand">
              <span className="brandMark">Rx</span>
              <div>
                <span className="brandName">PsychRx Assist</span>
                <span className="brandSub">Prescribing decision support</span>
              </div>
            </div>
            <nav className="nav">
              <a href="/">Assessment</a>
              <a href="/admin/rules">Rule library</a>
            </nav>
            <span className="cliniciansTag">For qualified clinicians</span>
          </div>
        </header>
        {children}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
