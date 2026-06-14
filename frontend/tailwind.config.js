/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // cool graphite surfaces — deliberate, desaturated, no pure black
        ink: {
          950: "#070910",
          900: "#0b0e15",
          850: "#10141c",
          800: "#171d27",
          700: "#212834",
        },
        line: {
          DEFAULT: "rgba(150,162,182,0.10)",
          strong: "rgba(150,162,182,0.18)",
        },
        dim: "#8d94a1",
        faint: "#59616f",
        // single restrained accent (steel-electric blue) with shades
        accent: {
          DEFAULT: "#4f8fca",
          300: "#8ab7e2",
          400: "#67a2d7",
          500: "#4f8fca",
          600: "#3d72a6",
          dim: "#35628d",
        },
        positive: "#57b389", // live / complete
        warn: "#d2a24a", // attention
        alert: "#d2685c", // overdue / error
      },
      fontFamily: {
        mono: ["ui-monospace", "SF Mono", "JetBrains Mono", "Cascadia Code", "Menlo", "monospace"],
      },
      borderRadius: {
        // sharper, more instrument-like corners
        md: "0.25rem",
        lg: "0.3125rem",
        xl: "0.4375rem",
        "2xl": "0.625rem",
      },
    },
  },
  plugins: [],
};
