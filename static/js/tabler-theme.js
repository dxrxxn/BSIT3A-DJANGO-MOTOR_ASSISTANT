/*!
 * Tabler v1.4.0 (https://tabler.io)
 * J.A.R.V.I.S. Theme Integration & Custom Background Color Engine
 */
(function () {
  'use strict';

  // 1. Color Math Utilities for Arbitrary Background Adjustment
  function hexToRgb(hex) {
    if (!hex) return null;
    hex = String(hex).replace('#', '').trim();
    if (hex.length === 3) {
      hex = hex.split('').map(function (c) { return c + c; }).join('');
    }
    if (hex.length !== 6) return null;
    var num = parseInt(hex, 16);
    if (isNaN(num)) return null;
    return {
      r: (num >> 16) & 255,
      g: (num >> 8) & 255,
      b: num & 255
    };
  }

  function rgbToHex(r, g, b) {
    function clamp(v) { return Math.max(0, Math.min(255, Math.round(v))); }
    return '#' + [clamp(r), clamp(g), clamp(b)].map(function (x) {
      return x.toString(16).padStart(2, '0');
    }).join('');
  }

  function blend(rgb, targetVal, amount) {
    return {
      r: rgb.r + (targetVal - rgb.r) * amount,
      g: rgb.g + (targetVal - rgb.g) * amount,
      b: rgb.b + (targetVal - rgb.b) * amount
    };
  }

  function getLuminance(rgb) {
    return (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
  }

  function applyJarvisBg(hex) {
    if (!hex) return;
    var rgb = hexToRgb(hex);
    if (!rgb) return;

    var lum = getLuminance(rgb);
    var root = document.documentElement;

    if (lum < 0.5) {
      // Dark Base: surfaces slightly lighter, text white
      var sidebar = blend(rgb, 255, 0.05);
      var card = blend(rgb, 255, 0.085);
      var cardHover = blend(rgb, 255, 0.13);
      var input = blend(rgb, 255, 0.04);
      var borderCard = blend(rgb, 255, 0.18);
      var borderSubtle = blend(rgb, 255, 0.10);

      root.style.setProperty('--jarvis-bg-window', hex);
      root.style.setProperty('--jarvis-bg-workspace', hex);
      root.style.setProperty('--jarvis-bg-sidebar', rgbToHex(sidebar.r, sidebar.g, sidebar.b));
      root.style.setProperty('--jarvis-bg-card', rgbToHex(card.r, card.g, card.b));
      root.style.setProperty('--jarvis-bg-card-hover', rgbToHex(cardHover.r, cardHover.g, cardHover.b));
      root.style.setProperty('--jarvis-bg-input', rgbToHex(input.r, input.g, input.b));
      root.style.setProperty('--jarvis-border-card', rgbToHex(borderCard.r, borderCard.g, borderCard.b));
      root.style.setProperty('--jarvis-border-subtle', rgbToHex(borderSubtle.r, borderSubtle.g, borderSubtle.b));
      root.style.setProperty('--jarvis-text-primary', '#ffffff');
      root.style.setProperty('--jarvis-text-secondary', '#cbd5e1');
    } else {
      // Light Base: surfaces slightly darker, text dark
      var sidebarL = blend(rgb, 0, 0.04);
      var cardL = blend(rgb, 0, 0.07);
      var cardHoverL = blend(rgb, 0, 0.11);
      var inputL = blend(rgb, 255, 0.95);
      var borderCardL = blend(rgb, 0, 0.16);
      var borderSubtleL = blend(rgb, 0, 0.10);

      root.style.setProperty('--jarvis-bg-window', hex);
      root.style.setProperty('--jarvis-bg-workspace', hex);
      root.style.setProperty('--jarvis-bg-sidebar', rgbToHex(sidebarL.r, sidebarL.g, sidebarL.b));
      root.style.setProperty('--jarvis-bg-card', rgbToHex(cardL.r, cardL.g, cardL.b));
      root.style.setProperty('--jarvis-bg-card-hover', rgbToHex(cardHoverL.r, cardHoverL.g, cardHoverL.b));
      root.style.setProperty('--jarvis-bg-input', rgbToHex(inputL.r, inputL.g, inputL.b));
      root.style.setProperty('--jarvis-border-card', rgbToHex(borderCardL.r, borderCardL.g, borderCardL.b));
      root.style.setProperty('--jarvis-border-subtle', rgbToHex(borderSubtleL.r, borderSubtleL.g, borderSubtleL.b));
      root.style.setProperty('--jarvis-text-primary', '#0f172a');
      root.style.setProperty('--jarvis-text-secondary', '#334155');
    }
  }

  function resetJarvisBg() {
    var root = document.documentElement;
    root.style.removeProperty('--jarvis-bg-window');
    root.style.removeProperty('--jarvis-bg-workspace');
    root.style.removeProperty('--jarvis-bg-sidebar');
    root.style.removeProperty('--jarvis-bg-card');
    root.style.removeProperty('--jarvis-bg-card-hover');
    root.style.removeProperty('--jarvis-bg-input');
    root.style.removeProperty('--jarvis-border-card');
    root.style.removeProperty('--jarvis-border-subtle');
    root.style.removeProperty('--jarvis-text-primary');
    root.style.removeProperty('--jarvis-text-secondary');
    try {
      localStorage.removeItem('jarvis-custom-bg');
    } catch (e) {}
  }

  // Expose on window for runtime settings offcanvas & copilot components
  window.JarvisBg = {
    apply: function (hex) {
      applyJarvisBg(hex);
      try { localStorage.setItem('jarvis-custom-bg', hex); } catch (e) {}
    },
    reset: resetJarvisBg,
    hexToRgb: hexToRgb,
    rgbToHex: rgbToHex,
    getLuminance: getLuminance
  };

  // 2. Tabler Base Configurations
  var themeConfig = {
    "theme": "dark",
    "theme-base": "gray",
    "theme-font": "sans-serif",
    "theme-primary": "cyan",
    "theme-radius": "1"
  };

  var params = new URLSearchParams(window.location.search);

  for (var key in themeConfig) {
    var param = params.get(key);
    var selectedValue;
    if (param) {
      localStorage.setItem('tabler-' + key, param);
      selectedValue = param;
    } else {
      var stored = localStorage.getItem('tabler-' + key);
      // Default to dark theme for Jarvis Graphite Console
      selectedValue = (key === 'theme' && (!stored || stored === 'light')) ? 'dark' : (stored ? stored : themeConfig[key]);
      localStorage.setItem('tabler-' + key, selectedValue);
    }
    document.documentElement.setAttribute('data-bs-' + key, selectedValue);
  }

  // 3. Apply custom background immediately before DOM render
  try {
    var customBg = localStorage.getItem('jarvis-custom-bg');
    if (customBg) {
      applyJarvisBg(customBg);
    }
  } catch (e) {}
})();
