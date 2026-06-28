import type { Config } from "tailwindcss";

// InterOpera brand tokens (light theme, purple primary).
export default {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#6562E7", hover: "#5451D4", soft: "#ECECFA" },
        teal: "#73DFD7",
        violet: "#A5A6F6",
        bg: { DEFAULT: "#FFFFFF", soft: "#F6F6FB", muted: "#ECECFA" },
        line: { DEFAULT: "#E2E2F0", dark: "#C8C8E8" },
        ink: { 0: "#0B111D", 1: "#1E2A3B", 2: "#53627E", 3: "#8A96A8", 4: "#B8C0CC" },
        ok: { bg: "#E6F6F0", text: "#1A7A50", line: "#9ADBC0" },
        warn: { bg: "#FFF4E5", text: "#A85A00", line: "#FFD29E" },
        road: { bg: "#ECECFA", text: "#5451D4", line: "#A5A6F6" },
        danger: { bg: "#FDECEC", text: "#C0392B", line: "#F3B4B4" },
      },
      fontFamily: {
        sans: ["var(--font-lato)", "system-ui", "Arial", "sans-serif"],
      },
      borderRadius: { DEFAULT: "6px" },
    },
  },
  plugins: [],
} satisfies Config;
