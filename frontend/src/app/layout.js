import "./globals.css";
import Navbar from "@/components/Navbar";
import { Analytics } from "@vercel/analytics/react";

export const metadata = {
  title: "Insider Tracker — Polymarket Suspicious Activity Monitor",
  description:
    "Real-time detection and scoring of suspicious trading activity on Polymarket prediction markets.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main className="container" style={{ paddingBottom: "var(--space-12)", paddingTop: "var(--space-8)" }}>
          {children}
        </main>
        <Analytics />
      </body>
    </html>
  );
}
