import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Meridian Compliance",
  description: "Audit-defensible compliance reporting over a knowledge graph",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
