import type { Metadata, Viewport } from "next";
import { STYLE_KEY, STYLES } from "@/lib/styles";
import { fontVariables } from "./fonts";
import "./globals.css";
import "./styles.css";

export const metadata: Metadata = {
  title: "Weather, with uncertainty",
  description: "A personal weather forecast that shows how sure the forecast is.",
  robots: { index: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f7f5" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1012" },
  ],
};

// Applies a saved light/dark choice and dashboard style before first paint to
// avoid a flash.
const styleIds = JSON.stringify(STYLES.map((s) => s.id).filter((id) => id !== "original"));
const themeScript = `try{var d=document.documentElement,t=localStorage.getItem("theme");if(t==="light"||t==="dark")d.dataset.theme=t;var s=localStorage.getItem("${STYLE_KEY}");if(${styleIds}.indexOf(s)>=0)d.dataset.style=s}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVariables} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
