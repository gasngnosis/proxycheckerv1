/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'azure-primary': '#007BFF',
        'azure-background': '#F0F8FF',
        'azure-success': '#28A745',
        'azure-failure': '#DC3545',
      },
    },
  },
  plugins: [],
}