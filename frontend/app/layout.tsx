import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PsychRx Assist — Clinical Decision Support",
  description: "Psychiatry prescribing decision-support for clinicians",
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
      </body>
    </html>
  );
}
