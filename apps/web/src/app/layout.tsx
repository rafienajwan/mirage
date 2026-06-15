import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans, Instrument_Serif } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
});

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
      className={`${inter.variable} ${plusJakarta.variable} ${instrumentSerif.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col bg-[#060816] text-white overflow-x-hidden">
        {children}
      </body>
    </html>
  );
}

