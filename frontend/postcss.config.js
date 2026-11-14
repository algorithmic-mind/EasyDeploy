import rtlcss from 'postcss-rtlcss'

// One stylesheet for both directions: [dir="rtl"] rules are generated automatically (§10.4).
export default {
  plugins: [rtlcss({ mode: 'combined' })],
}
