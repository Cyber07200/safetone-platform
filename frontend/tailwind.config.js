/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // SF Pro on Apple devices, Inter everywhere else.
        sans: ["-apple-system", "BlinkMacSystemFont", "'SF Pro Text'", "'Inter Variable'", "Inter", "system-ui", "Segoe UI", "sans-serif"],
        display: ["-apple-system", "BlinkMacSystemFont", "'SF Pro Display'", "'Inter Variable'", "Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "'SF Mono'", "'JetBrains Mono Variable'", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        // Apple-like neutrals: 950 = #1D1D1F text, 50 = #F5F5F7 surface.
        ink: { 950: "#111113", 900: "#1D1D1F", 800: "#333336", 700: "#424245", 600: "#6E6E73", 500: "#6E6E73", 400: "#86868B", 300: "#C7C7CC", 200: "#D2D2D7", 100: "#E8E8ED", 50: "#F5F5F7" },
        brand: { 900: "#003A7A", 800: "#004FA3", 700: "#0066CC", 600: "#0071E3", 500: "#0077ED", 400: "#2997FF", 200: "#B8DAFF", 100: "#DCEBFF", 50: "#EEF5FF" },
        ok: { 700: "#1A7F37", 600: "#248A3D", 100: "#D7F2DE", 50: "#EEF9F1" },
        warn: { 700: "#A35200", 600: "#C76A00", 100: "#FFEBCC", 50: "#FFF7EB" },
        bad: { 700: "#C4221B", 600: "#E0281F", 100: "#FFE0DE", 50: "#FFF2F1" },
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,.04), 0 4px 16px -6px rgba(0,0,0,.06)",
        lift: "0 24px 60px -24px rgba(0,0,0,.22), 0 4px 14px rgba(0,0,0,.05)",
        glow: "0 30px 80px -30px rgba(0,113,227,.45)",
      },
      borderRadius: { xl2: "18px", "4xl": "28px" },
      transitionTimingFunction: { apple: "cubic-bezier(0.16, 1, 0.3, 1)" },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(12px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: { "fade-up": "fade-up .7s cubic-bezier(0.16,1,0.3,1) both" },
    },
  },
  plugins: [],
};
