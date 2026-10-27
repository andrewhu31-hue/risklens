/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Public Sans"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      colors: {
        paper: "#F4F5F7",
        panel: "#FFFFFF",
        ink: { DEFAULT: "#141A24", soft: "#2B3340" },
        muted: { DEFAULT: "#5A6372", faint: "#8A929F" },
        rule: { DEFAULT: "#DCE0E6", soft: "#EBEDF1" },
        data: "#2D47C8",
        gain: "#0E7C55",
        loss: "#B8382A",
        caution: "#8A5A00",
      },
      borderRadius: {
        panel: "6px",
      },
    },
  },
  plugins: [],
};
