const adminPreset = require('./src/styles/tailwind.preset.cjs')

module.exports = {
  presets: [adminPreset],
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
