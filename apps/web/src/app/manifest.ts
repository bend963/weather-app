import type { MetadataRoute } from "next";

/** Lets Chrome and Safari install the site as a full-screen home-screen app. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Weather, with uncertainty",
    short_name: "Weather",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f7f7f5",
    theme_color: "#f7f7f5",
    icons: [
      { src: "/icon0.png", sizes: "192x192", type: "image/png" },
      { src: "/icon1.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
