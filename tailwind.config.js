/** Sistema de diseño "Campo Directo": verde de campo, terracota, amarillo cálido y neutros tierra.
 *  Texto sobre 600/700 de primary y secondary cumple contraste AA (>= 4.5:1) con blanco. */
module.exports = {
  content: ["./app/templates/**/*.html", "./app/static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#F1F8EE", 100: "#DDEFD5", 200: "#BCE0AE", 300: "#93CB7F", 400: "#66AE4F",
          500: "#478F33", 600: "#377427", 700: "#2E5D22", 800: "#264A1E", 900: "#1F3D1B",
        },
        secondary: {
          50: "#FDF4EF", 100: "#FAE3D6", 200: "#F4C4AA", 300: "#EC9D77", 400: "#E0764A",
          500: "#CF5B2E", 600: "#B64A24", 700: "#953B1F", 800: "#7A311E", 900: "#662B1B",
        },
        sol: {
          50: "#FFFBEB", 100: "#FEF3C7", 200: "#FDE68A", 300: "#FCD34D", 400: "#F8BE2B",
          500: "#E5A210", 600: "#B7790A", 700: "#8F5A0C",
        },
        tierra: {
          50: "#FAF8F5", 100: "#F3EFE9", 200: "#E7E0D6", 300: "#D5CABB", 400: "#B3A594",
          500: "#8A7D6D", 600: "#6B6054", 700: "#51483F", 800: "#393229", 900: "#241F19",
        },
        whatsapp: { DEFAULT: "#0A7C66", dark: "#075E4E" },
      },
      fontFamily: {
        sans: ["Nunito", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        display: ["Fraunces", "Georgia", "Cambria", "serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(57,50,41,.08), 0 4px 12px rgba(57,50,41,.06)",
      },
      borderRadius: { xl2: "1.25rem" },
    },
  },
  plugins: [],
};
