import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg-base)",
        foreground: "var(--text-primary)",
        surface: "var(--bg-surface)",
        panel: "var(--bg-panel)",
        card: "var(--bg-card)",
        primary: {
          DEFAULT: "var(--color-primary)",
          light: "var(--color-primary-light)",
        },
        gold: {
          DEFAULT: "var(--color-gold)",
          dark: "var(--color-gold-dark)",
        },
      },
      fontFamily: {
        display:  ["Space Grotesk", "sans-serif"],
        body:     ["Inter", "sans-serif"],
        datatype: ["Datatype", "var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      keyframes: {
        "modal-in": {
          "0%": { opacity: "0", transform: "scale(0.96) translateY(8px)" },
          "100%": { opacity: "1", transform: "scale(1) translateY(0)" },
        },
        "slide-up": {
          "0%": { transform: "translateY(100%)" },
          "100%": { transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        "modal-in": "modal-in 0.18s ease-out forwards",
        "slide-up": "slide-up 0.25s ease-out forwards",
        "fade-in":  "fade-in 0.2s ease-out forwards",
      },
    },
  },
  plugins: [],
};
export default config;
