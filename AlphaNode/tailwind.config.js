/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      colors: {
        // Bloomberg-terminal-inspired dark palette
        ink: {
          900: "#0a0e14",
          800: "#0f1620",
          700: "#151d2b",
          600: "#1c2738",
          500: "#26344a",
        },
        accent: {
          DEFAULT: "#f0b429",
          soft: "#fde68a",
        },
        bull: "#22c55e",
        bear: "#ef4444",
      },
    },
  },
  plugins: [],
};
