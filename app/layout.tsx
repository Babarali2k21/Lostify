import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lostify",
  description: "Lostify helps students and staff report, find, and recover lost items across the University campus.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
