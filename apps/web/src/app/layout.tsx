import type { Metadata } from "next";
import { Figtree, Syne } from "next/font/google";
import type { CSSProperties, ReactNode } from "react";

import { AppProviders } from "@/shared/ui/AppProviders";
import { SiteHeader } from "@/shared/ui/SiteHeader";

import "./globals.css";

const brand = Syne({
  subsets: ["latin"],
  variable: "--font-brand-loaded",
  weight: ["600", "700", "800"],
});

const body = Figtree({
  subsets: ["latin"],
  variable: "--font-body-loaded",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Alama",
  description: "Autonomous AI software engineering",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${brand.variable} ${body.variable}`}>
      <body
        style={
          {
            ["--font-brand"]: "var(--font-brand-loaded), Syne, sans-serif",
            ["--font-body"]: "var(--font-body-loaded), Figtree, sans-serif",
          } as CSSProperties
        }
      >
        <AppProviders>
          <SiteHeader />
          <main>{children}</main>
        </AppProviders>
      </body>
    </html>
  );
}
