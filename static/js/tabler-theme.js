/*!
 * Tabler v1.4.0 (https://tabler.io)
 * J.A.R.V.I.S. Theme Integration
 */
(function () {
  'use strict';

  const themeConfig = {
    "theme": "dark",
    "theme-base": "gray",
    "theme-font": "sans-serif",
    "theme-primary": "cyan",
    "theme-radius": "1"
  };

  const params = new URLSearchParams(window.location.search);

  for (const key in themeConfig) {
    const param = params.get(key);
    let selectedValue;
    if (param) {
      localStorage.setItem('tabler-' + key, param);
      selectedValue = param;
    } else {
      const stored = localStorage.getItem('tabler-' + key);
      selectedValue = stored ? stored : themeConfig[key];
    }
    document.documentElement.setAttribute('data-bs-' + key, selectedValue);
  }
})();
