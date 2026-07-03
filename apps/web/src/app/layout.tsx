import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project MIRAGE | Autonomous AI Cyber Deception & Defense Platform",
  description: "Project MIRAGE is an autonomous enterprise cybersecurity platform that uses AI risk scoring, real-time threat intelligence, and intelligent decoy environments to intercept and neutralize advanced threats.",
  keywords: ["AI cybersecurity", "anomaly detection", "threat hunting", "decoy environment", "autonomous deception", "threat intelligence", "Project MIRAGE"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased dark"
    >
      <body className="min-h-full flex flex-col bg-[#060816] text-white overflow-x-hidden">
        {children}
      </body>
    </html>
  );
}

