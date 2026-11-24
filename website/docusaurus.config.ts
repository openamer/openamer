import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const ALL_LOCALES = [
  'en',
  'zh-Hans',
  'de',
  'es',
  'fr',
  'pt-BR',
  'ru',
  'ja',
  'ko',
  'hi',
  'ar',
  'it',
  'tr',
  'id',
];

/**
 * Which locales a build covers.
 *
 * Measured 2026-11-24: the full 14-locale build does not fit the 20-minute
 * budget of the `docs-site-checks` PR gate (the job ran 21:28:37 -> 21:48:53 and
 * was cancelled inside "Build Docusaurus"). On `main` that gate is red, so
 * "All required checks pass" fails for every PR and nothing can merge through
 * the normal path. The all-locale build belongs to the deploy: deploy-site runs
 * it on main with a 180-minute budget.
 *
 * So a pull_request build covers the source locale only. That still compiles
 * every generated skill page, which is the class of error this gate exists to
 * catch (an MDX fault in the English source); translated overlays are copies of
 * those pages and stay covered by the deploy build and by
 * `scripts/i18n_verify_locales.py`.
 *
 * Override with DOCUSAURUS_LOCALES=all (or a comma list) for a deliberate full
 * build outside CI.
 */
function buildLocales(): string[] {
  const override = (process.env.DOCUSAURUS_LOCALES || '').trim();
  if (override === 'all') return ALL_LOCALES;
  if (override) {
    const wanted = override
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    const unknown = wanted.filter((value) => !ALL_LOCALES.includes(value));
    if (unknown.length) {
      throw new Error(
        `DOCUSAURUS_LOCALES names unknown locale(s): ${unknown.join(', ')}. ` +
          `Known: ${ALL_LOCALES.join(', ')}`,
      );
    }
    return wanted.length ? wanted : ['en'];
  }
  // GitHub sets GITHUB_EVENT_NAME in every Actions job.
  if (process.env.GITHUB_EVENT_NAME === 'pull_request') return ['en'];
  return ALL_LOCALES;
}

const config: Config = {
  title: 'OpenAmer Agent',
  tagline: 'The self-improving AI agent',
  favicon: 'img/favicon.ico',

  url: 'https://openamer.com',
  baseUrl: '/docs/',

  organizationName: 'openamer',
  projectName: 'openamer-agent',

  onBrokenLinks: 'warn',

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: buildLocales(),
    localeConfigs: {
      en: {
        label: 'English',
        htmlLang: 'en',
      },
      'zh-Hans': {
        label: '简体中文',
        htmlLang: 'zh-Hans',
      },
      de: {
        label: 'Deutsch',
        htmlLang: 'de',
      },
      es: {
        label: 'Español',
        htmlLang: 'es',
      },
      fr: {
        label: 'Français',
        htmlLang: 'fr',
      },
      'pt-BR': {
        label: 'Português (Brasil)',
        htmlLang: 'pt-BR',
      },
      ru: {
        label: 'Русский',
        htmlLang: 'ru',
      },
      ja: {
        label: '日本語',
        htmlLang: 'ja',
      },
      ko: {
        label: '한국어',
        htmlLang: 'ko',
      },
      hi: {
        label: 'हिन्दी',
        htmlLang: 'hi',
      },
      ar: {
        label: 'العربية',
        htmlLang: 'ar',
        direction: 'rtl',
      },
      it: {
        label: 'Italiano',
        htmlLang: 'it',
      },
      tr: {
        label: 'Türkçe',
        htmlLang: 'tr',
      },
      id: {
        label: 'Bahasa Indonesia',
        htmlLang: 'id',
      },
    },
  },

  themes: [
    '@docusaurus/theme-mermaid',
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      /** @type {import("@easyops-cn/docusaurus-search-local").PluginOptions} */
      ({
        hashed: true,
        language: ['en', 'zh'],
        indexBlog: false,
        docsRouteBasePath: '/',
        // Disabled: appends ?_highlight=... to URLs (before the #anchor),
        // which makes copy/pasted doc links ugly. Ctrl+F on the page is fine.
        highlightSearchTermsOnTargetPage: false,
        // Exclude the auto-generated per-skill catalog pages from search.
        // There are hundreds of them and they dominate results for generic
        // terms, drowning out the real user-guide / reference docs.
        // The two human-written catalog indexes (reference/skills-catalog,
        // reference/optional-skills-catalog) remain indexed.
        //
        // Note: ignoreFiles matches `route` (baseUrl stripped, no leading
        // slash). With baseUrl '/docs/', `/docs/user-guide/skills/bundled/x`
        // becomes 'user-guide/skills/bundled/x'.
        ignoreFiles: [
          /^user-guide\/skills\/bundled\//,
          /^user-guide\/skills\/optional\//,
        ],
        // Exact-or-prefix matching only (default is edit distance 1).
        // With fuzzy distance 1, "keet" matched "meetings"/"keep" (one
        // edit away after stemming), and multi-word typo queries against
        // our ~14 MB index could stall the single-threaded search worker
        // for 25s+, backing up every subsequent keystroke's search until
        // the bar appeared dead. Distance 0 keeps "word or its extension"
        // semantics (keet -> keet*) and removes the pathological scans.
        fuzzyMatchingDistance: 0,
      }),
    ],
  ],

  plugins: [
    [
      '@docusaurus/plugin-client-redirects',
      {
        // Static-host redirects for renamed doc pages (GitHub Pages can't
        // do server-side redirects). Paths are relative to baseUrl (/docs/).
        redirects: [
          {
            // Renamed in #44470 (Automation Blueprints terminology rebrand)
            from: '/guides/automation-templates',
            to: '/guides/automation-blueprints',
          },
          {
            // Moved when the Plugins subcategory was created under
            // Developer Guide > Extending (docs restructure, July 2026)
            from: '/guides/build-a-openamer-plugin',
            to: '/developer-guide/plugins',
          },
        ],
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',  // Docs at the root of /docs/
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/openamer/openamer/edit/main/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/openamer-agent-banner.png',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: true,
      },
    },
    navbar: {
      title: 'OpenAmer Agent',
      logo: {
        alt: 'OpenAmer Agent',
        src: 'img/logo.png',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docs',
          position: 'left',
          label: 'Docs',
        },
        {
          to: '/skills',
          label: 'Skills',
          position: 'left',
        },
        {
          href: 'https://github.com/openamer/openamer/',
          label: 'Download',
          position: 'left',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
        {
          href: 'https://github.com/openamer/openamer',
          label: 'Home',
          position: 'right',
        },
        {
          href: 'https://github.com/openamer/openamer',
          label: 'GitHub',
          position: 'right',
        },
        {
          href: 'https://discord.gg/openamer',
          label: 'Discord',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            { label: 'Getting Started', to: '/getting-started/quickstart' },
            { label: 'User Guide', to: '/user-guide/cli' },
            { label: 'Developer Guide', to: '/developer-guide/architecture' },
            { label: 'Reference', to: '/reference/cli-commands' },
          ],
        },
        {
          title: 'Community',
          items: [
            { label: 'Discord', href: 'https://discord.gg/openamer' },
            { label: 'GitHub Issues', href: 'https://github.com/openamer/openamer/issues' },
            { label: 'Skills Hub', href: 'https://agentskills.io' },
          ],
        },
        {
          title: 'More',
          items: [
            { label: 'Desktop Download', href: 'https://github.com/openamer/openamer/' },
            { label: 'GitHub', href: 'https://github.com/openamer/openamer' },
            { label: 'OpenAmer', href: 'https://openamer.com' },
          ],
        },
      ],
      copyright: `Built by <a href="https://openamer.com">OpenAmer</a> · MIT License · ${new Date().getFullYear()}`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'yaml', 'json', 'python', 'toml'],
    },
    mermaid: {
      theme: {light: 'neutral', dark: 'dark'},
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
