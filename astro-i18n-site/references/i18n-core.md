# i18n Core Module

## src/i18n/index.js

```javascript
import en from './locales/en.json';
import zh from './locales/zh.json';
import ja from './locales/ja.json';
import de from './locales/de.json';
import fr from './locales/fr.json';

export const DEFAULT_LANG = 'en';

export const LANGUAGES = {
  en: { label: 'EN', name: 'English' },
  zh: { label: '中文', name: '中文' },
  ja: { label: '日本語', name: '日本語' },
  de: { label: 'DE', name: 'Deutsch' },
  fr: { label: 'FR', name: 'Français' },
};

const translations = { en, zh, ja, de, fr };

export function getTranslation(lang) {
  const base = translations[DEFAULT_LANG];
  const target = translations[lang];
  if (!target || lang === DEFAULT_LANG) return base;
  return { ...base, ...target };
}

export function getLangFromUrl(url) {
  const [, lang] = url.pathname.split('/');
  if (lang in LANGUAGES && lang !== DEFAULT_LANG) return lang;
  return DEFAULT_LANG;
}

export function getLocalePath(lang) {
  if (lang === DEFAULT_LANG) return '/';
  return `/${lang}/`;
}
```

## Design Decisions

**Spread merge for translations:** `{ ...base, ...target }` means non-default locales only need to override keys they translate. Missing keys automatically fall back to English. This avoids maintaining complete translation files for every locale.

**No i18n plugin:** Astro's built-in i18n routing (`i18n` config in `astro.config.mjs`) adds middleware overhead and isn't needed for static sites. The custom approach gives full control over URL structure.

**LANGUAGES object:** Dual labels — `label` for compact display (nav bar), `name` for full display (dropdown). This avoids computing display names at runtime.

**getLangFromUrl:** Only checks the first path segment. Returns default lang for any unrecognized prefix, which handles API routes and other non-localized paths gracefully.

## Translation File Structure

```
src/i18n/locales/
├── en.json    # ~170 keys, MUST be complete (it's the fallback)
├── zh.json    # Can be partial — missing keys fall back to en
├── ja.json
├── de.json
└── fr.json
```

### Key naming convention

```json
{
  "navFeatures": "Features",
  "navCompare": "Compare",
  "heroTitleLine1": "Your headline here,",
  "heroDescription": "Your product description...",
  "seoHomeTitle": "MyApp — Your tagline here",
  "seoHomeDescription": "...",
  "seoHomeJsonLdDescription": "...",
  "blogIndexTitle": "Blog — MyApp",
  "blogBackToBlog": "← Back to Blog",
  "blogShareThisPost": "Share this post",
  "blogTagAll": "All",
  "langBannerMessage": "This page is available in your language",
  "langBannerSwitch": "Switch",
  "faq1Q": "What is MyApp?",
  "faq1A": "MyApp is..."
}
```

**Prefixes group related strings:**
- `nav*` — navigation
- `hero*` — hero section
- `seo*` — SEO meta tags and JSON-LD
- `blog*` — blog UI
- `langBanner*` — language detection banner
- `faq*Q` / `faq*A` — FAQ question/answer pairs

## Adding a New Locale

1. Create `src/i18n/locales/{code}.json` with translated keys
2. Add import and entry to `translations` in `index.js`
3. Add entry to `LANGUAGES` object with `label` and `name`
4. Add `hreflangPairs` entries in all page files
5. Create matching blog content in `src/content/blog/{code}/`
6. Test language switcher path generation
