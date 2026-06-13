/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#06080d",
          900: "#0a0d13",
          850: "#0e121a",
          800: "#161b24",
          700: "#1d2430",
        },
        line: {
          DEFAULT: "rgba(148,163,184,0.10)",
          strong: "rgba(148,163,184,0.16)",
        },
        dim: "#8b94a5",
        faint: "#586273",
        accent: "#4aa8ff",
      },
      fontFamily: {
        mono: ["ui-monospace", "SF Mono", "JetBrains Mono", "Cascadia Code", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
