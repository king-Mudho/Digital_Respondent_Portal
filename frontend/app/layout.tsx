import type { Metadata, Viewport } from "next";
import "@/styles/globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "ABF-FST Digital Respondent Portal",
  description:
    "Research-operations portal for the ABF-FST study (Chinhoyi University of Technology). Invitation-only.",
  // Defence in depth against accidental discovery, on top of the invitation-
  // token access gate -- see docs/20_EMBEDDING_WITH_ABI.md.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1c3a5e",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
