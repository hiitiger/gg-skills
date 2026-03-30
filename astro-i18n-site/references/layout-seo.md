# Layout & SEO

## Base Layout (Layout.astro)

```astro
---
// src/layouts/Layout.astro
import Navbar from '../components/Navbar.jsx';
import LanguageBanner from '../components/LanguageBanner.jsx';
import { getTranslation } from '../i18n/index.js';

interface Props {
  lang: string;
  title: string;
  description?: string;
  canonical?: string;
  hreflangPairs?: { lang: string; url: string }[];
  ogImage?: string;
  publishedTime?: string;
  articleTags?: string[];
}

const {
  lang,
  title,
  description,
  canonical,
  hreflangPairs,
  ogImage,
  publishedTime,
  articleTags,
} = Astro.props;

const t = getTranslation(lang);

const ogLocaleMap: Record<string, string> = {
  en: 'en_US',
  zh: 'zh_CN',
  ja: 'ja_JP',
  de: 'de_DE',
  fr: 'fr_FR',
};
const ogLocale = ogLocaleMap[lang] || lang;
---

<!doctype html>
<html lang={lang}>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    {description && <meta name="description" content={description} />}

    {/* Canonical URL */}
    {canonical && <link rel="canonical" href={canonical} />}

    {/* hreflang tags for all locales + x-default */}
    {hreflangPairs?.map(({ lang: l, url }) => (
      <link rel="alternate" hreflang={l} href={url} />
    ))}
    {hreflangPairs && (
      <link rel="alternate" hreflang="x-default"
        href={hreflangPairs.find((p) => p.lang === 'en')?.url ?? '/'} />
    )}

    {/* Open Graph */}
    <meta property="og:title" content={title} />
    {description && <meta property="og:description" content={description} />}
    <meta property="og:locale" content={ogLocale} />
    <meta property="og:type" content={publishedTime ? 'article' : 'website'} />
    {ogImage && <meta property="og:image" content={ogImage} />}
    {publishedTime && <meta property="article:published_time" content={publishedTime} />}
    {articleTags?.map((tag) => (
      <meta property="article:tag" content={tag} />
    ))}

    {/* JSON-LD (landing page example) */}
    {!publishedTime && (
      <script type="application/ld+json" set:html={JSON.stringify({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": title,
        "url": canonical || import.meta.env.SITE,
        "inLanguage": lang,
        "description": description || t.seoHomeJsonLdDescription,
      })} />
    )}
  </head>
  <body>
    <Navbar client:load lang={lang} currentPath={Astro.url.pathname} />
    <LanguageBanner client:load lang={lang} currentPath={Astro.url.pathname} />
    <slot />
  </body>
</html>
```

## Blog Layout (BlogLayout.astro)

```astro
---
// src/layouts/BlogLayout.astro
import Layout from './Layout.astro';
import { LANGUAGES, DEFAULT_LANG, getTranslation } from '../i18n/index.js';

interface Props {
  lang: string;
  title: string;
  description: string;
  date: Date;
  tags: string[];
  slug: string;
}

const { lang, title, description, date, tags, slug } = Astro.props;
const t = getTranslation(lang);

// Build hreflang pairs dynamically from LANGUAGES
const hreflangPairs = Object.keys(LANGUAGES).map((l) => ({
  lang: l,
  url: l === DEFAULT_LANG
    ? `${import.meta.env.SITE}/blog/${slug}/`
    : `${import.meta.env.SITE}/${l}/blog/${slug}/`,
}));

const canonical = lang === DEFAULT_LANG
  ? `${import.meta.env.SITE}/blog/${slug}/`
  : `${import.meta.env.SITE}/${lang}/blog/${slug}/`;

// Locale-aware date formatting
const localeMap: Record<string, string> = {
  en: 'en-US', zh: 'zh-CN', ja: 'ja-JP', de: 'de-DE', fr: 'fr-FR',
};
const formattedDate = new Intl.DateTimeFormat(localeMap[lang] || lang, {
  year: 'numeric', month: 'long', day: 'numeric',
}).format(date);

// JSON-LD structured data
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "BlogPosting",
      "headline": title,
      "description": description,
      "inLanguage": lang,
      "datePublished": date.toISOString(),
      "url": canonical,
      "keywords": tags,
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": t.navHome || "Home",
          "item": lang === DEFAULT_LANG ? import.meta.env.SITE : `${import.meta.env.SITE}/${lang}/` },
        { "@type": "ListItem", "position": 2, "name": "Blog",
          "item": lang === DEFAULT_LANG ? `${import.meta.env.SITE}/blog/` : `${import.meta.env.SITE}/${lang}/blog/` },
        { "@type": "ListItem", "position": 3, "name": title },
      ],
    },
  ],
};
---

<Layout
  lang={lang}
  title={`${title} — Blog`}
  description={description}
  canonical={canonical}
  hreflangPairs={hreflangPairs}
  publishedTime={date.toISOString()}
  articleTags={tags}
>
  <script type="application/ld+json" set:html={JSON.stringify(jsonLd)} />

  <article class="mx-auto max-w-3xl px-4 py-12">
    <header class="mb-8">
      <a href={lang === DEFAULT_LANG ? '/blog/' : `/${lang}/blog/`}
         class="text-sm text-cyan-600 hover:underline">
        {t.blogBackToBlog}
      </a>
      <h1 class="mt-4 text-3xl font-bold">{title}</h1>
      <time datetime={date.toISOString()} class="text-sm text-slate-500">
        {formattedDate}
      </time>
      <div class="mt-2 flex gap-2">
        {tags.map((tag) => (
          <span class="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{tag}</span>
        ))}
      </div>
    </header>

    <div class="prose prose-slate max-w-none">
      <slot />
    </div>

    <footer class="mt-12 border-t pt-6">
      <p class="text-sm font-medium">{t.blogShareThisPost}</p>
      {/* Social share links using canonical URL */}
    </footer>
  </article>
</Layout>
```

## Design Decisions

**`ogLocaleMap`:** Open Graph requires full locale codes (`zh_CN` not `zh`). The map covers common locales; extend it when adding new languages.

**`x-default` hreflang:** Always points to the English (default locale) URL as the fallback for search engines to use when no locale matches.

**`import.meta.env.SITE`:** Use Astro's built-in `site` config instead of hardcoding the domain. Set it in `astro.config.mjs`:

```javascript
export default defineConfig({
  site: 'https://yourdomain.com',
});
```

**JSON-LD separation:** Layout.astro renders `WebSite` schema for landing pages. BlogLayout.astro adds `BlogPosting` + `BreadcrumbList` via a separate `<script>` tag, both with `inLanguage` set per locale.
