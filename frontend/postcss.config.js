import rtlcss from 'postcss-rtlcss'

// One stylesheet for both directions: [dir="rtl"] rules are generated automatically (§10.4).
const rtl = rtlcss({ mode: 'combined' })

// Widgets that always render left-to-right inside `dir="ltr"` islands keep their CSS untouched:
// in combined mode both the [dir="ltr"] and [dir="rtl"] variants would match inside an island on an
// RTL page (e.g. xterm's measure element got both `left` and `right` and a huge width).
const LTR_ONLY = /[\\/]node_modules[\\/](@xterm|monaco-editor)[\\/]/

export default {
  plugins: [
    {
      postcssPlugin: 'easydeploy-rtlcss',
      Once(root, helpers) {
        if (LTR_ONLY.test(root.source?.input.file ?? '')) return
        return rtl.Once(root, helpers)
      },
    },
  ],
}
