/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        surface: "rgba(255,255,255,0.03)",
        border: "rgba(255,255,255,0.08)",
      },
    },
  },
  plugins: [],
};
