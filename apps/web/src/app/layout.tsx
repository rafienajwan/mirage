import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project MIRAGE | API Cyber Deception Gateway",
  description: "Project MIRAGE scores API requests for risk, routes suspicious traffic into decoy environments, and records attacker behavior for defenders.",
  keywords: ["API security", "anomaly detection", "decoy environment", "cyber deception", "threat intelligence", "Project MIRAGE"],
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

