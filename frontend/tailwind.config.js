```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html",
    "./backend/templates/**/*.{html,js}",
    "./frontend/src/**/*.{js,jsx,ts,tsx}", // Add this line for React app
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}

```