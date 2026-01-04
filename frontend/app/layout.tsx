import type { Metadata } from "next";
import { Geist, Geist_Mono, Mona_Sans, Roboto } from "next/font/google";
import "./globals.css";
import { ClerkProvider, GoogleOneTap } from "@clerk/nextjs";

const fonts = Roboto({
  variable: "--font-mona-sans",
  weight: ["200", "300", "400", "500", "600", "700", "800", "900"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  display: "swap",
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${fonts.className} antialiased`}>
        <ClerkProvider>
          <GoogleOneTap />
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
