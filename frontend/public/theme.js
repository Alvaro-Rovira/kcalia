// Aplica el tema antes del primer pintado para que no haya destello. Va en un fichero
// aparte (y no en línea) para poder mantener una CSP sin 'unsafe-inline' en scripts.
(function () {
  var COLORS = { dark: '#0b0c0e', light: '#f6f5f1' }
  function resolve(pref) {
    if (pref === 'light' || pref === 'dark') return pref
    if (pref === 'auto') return matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
    return 'dark'
  }
  function apply() {
    var pref = 'dark'
    try { pref = localStorage.getItem('kcalia:theme') || 'dark' } catch (e) {}
    var theme = resolve(pref)
    document.documentElement.dataset.theme = theme
    var meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', COLORS[theme])
  }
  apply()
  window.__kcaliaApplyTheme = apply
  matchMedia('(prefers-color-scheme: light)').addEventListener('change', apply)
})()
