/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dce7ff",
          500: "#3d63f5",
          600: "#2f4fd6",
          700: "#263fac",
        },
      },
    },
  },
  plugins: [],
};
