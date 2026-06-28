import "./globals.css";
import type { Metadata } from "next";
import { Lato } from "next/font/google";

const lato = Lato({
  weight: ["400", "700", "900"],
  subsets: ["latin"],
  variable: "--font-lato",
});

export const metadata: Metadata = {
  title: "Aegis — Auditable compliance engine",
  description:
    "Aegis: Auditable Engine for Graph-Integrated Source-tracking. Every reported "
    + "figure is computed deterministically, traced through a knowledge graph to its "
    + "source, and reconciled to the firm's answer key.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={lato.variable}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
