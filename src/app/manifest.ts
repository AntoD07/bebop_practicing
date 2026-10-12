import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Bebop practice",
    short_name: "Bebop",
    description: "Bebop cell practice with Gypsy-jazz fingering tabs.",
    start_url: "/connections",
    display: "standalone",
    background_color: "#fbfaf7",
    theme_color: "#1a3a8f",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
