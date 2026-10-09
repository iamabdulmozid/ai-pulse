/** Karbar Pulse — Tailwind config (standalone CLI, no Node pipeline).
 *  Colors map to the CSS variables in static/css/theme-tokens.css so utilities follow the theme. */
module.exports = {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './static/src/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        surface2: 'var(--surface2)',
        surface3: 'var(--surface3)',
        border: 'var(--border)',
        hair: 'var(--hair)',
        text: 'var(--text)',
        text2: 'var(--text2)',
        muted: 'var(--muted)',
        faint: 'var(--faint)',
        accent: 'var(--accent)',
        'on-accent': 'var(--on-accent)',
        ai: 'var(--ai)',
        status: {
          ok: 'var(--ok)',
          watch: 'var(--watch)',
          risk: 'var(--risk)',
          crit: 'var(--crit)',
          late: 'var(--late)',
          ship: 'var(--ship)',
          noupd: 'var(--noupd)',
        },
        stage: {
          knit: 'var(--knit)',
          link: 'var(--link)',
          mend: 'var(--mend)',
          iron: 'var(--iron)',
          pack: 'var(--pack)',
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: { card: 'var(--shadow)' },
    },
  },
  plugins: [],
};
