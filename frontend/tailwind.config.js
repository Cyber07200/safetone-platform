/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Inter Variable'", "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["'JetBrains Mono Variable'", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        ink: { 950: "#0B1220", 900: "#101A2E", 800: "#1B2740", 700: "#2E3B55", 600: "#4A5670", 500: "#667190", 400: "#8C95AD", 300: "#B7BECE", 200: "#DADFE8", 100: "#ECEFF4", 50: "#F5F7FA" },
        brand: { 900: "#0A2A8C", 800: "#0F35AE", 700: "#1440CC", 600: "#1846D8", 500: "#2F5FEA", 400: "#5B82F2", 200: "#C9D7FC", 100: "#E5ECFE", 50: "#F2F6FF" },
        ok: { 700: "#0B7A4B", 600: "#0E9259", 100: "#DDF4E8", 50: "#EFFAF4" },
        warn: { 700: "#9A5B00", 600: "#B86E00", 100: "#FDEFD3", 50: "#FFF8EA" },
        bad: { 700: "#B42318", 600: "#D92D20", 100: "#FDE3E1", 50: "#FEF3F2" },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,26,46,.04), 0 1px 1px rgba(16,26,46,.03)",
        lift: "0 12px 32px -12px rgba(16,26,46,.18), 0 2px 6px rgba(16,26,46,.05)",
      },
      borderRadius: { xl2: "14px" },
    },
  },
  plugins: [],
};
