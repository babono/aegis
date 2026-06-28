import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#0f172a", panel: "#111827" },
    },
  },
  plugins: [],
} satisfies Config;
