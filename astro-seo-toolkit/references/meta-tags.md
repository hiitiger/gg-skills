# Meta Tags Implementation

## Complete Layout.astro Head

```astro
---
const {
  lang = 'en',
  title,
  description,
  canonical,
  ogImage = '/og-default.png',
  type = 'website',
  jsonLd,
  hreflangPairs,
  noindex,
  publishedTime,
  articleTags,
} = Astro.props;

const t = getTranslation(lang);
const resolvedTitle = title ?? t.seoHomeTitle;
const resolvedDescription = description ?? t.seoHomeDescription;
const ogLocaleMap = {
  en: 'en_US', zh: 'zh_CN', ja: 'ja_JP', de: 'de_DE', fr: 'fr_FR',
};
const ogLocale = ogLocaleMap[lang] || 'en_US';
---

<html lang={lang}>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width" />

  {noindex && <meta name="robots" content="noindex, nofollow" />}

  <!-- Primary Meta -->
  <title>{resolvedTitle}</title>
  <meta name="description" content={resolvedDescription} />
  {canonical && <link rel="canonical" href={canonical} />}

  <!-- Open Graph -->
  <meta property="og:type" content={type} />
  <meta property="og:title" content={resolvedTitle} />
  <meta property="og:description" content={resolvedDescription} />
  <meta property="og:image" content={ogImage} />
  <meta property="og:locale" content={ogLocale} />
  {canonical && <meta property="og:url" content={canonical} />}

  <!-- Article Meta (blog posts only) -->
  {publishedTime && <meta property="article:published_time" content={publishedTime} />}
  {publishedTime && <meta property="article:modified_time" content={publishedTime} />}
  {articleTags && articleTags.map((tag) => (
    <meta property="article:tag" content={tag} />
  ))}

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:site" content="@yourhandle" />
  <meta name="twitter:title" content={resolvedTitle} />
  <meta name="twitter:description" content={resolvedDescription} />
  <meta name="twitter:image" content={ogImage} />

  <!-- Hreflang -->
  {hreflangPairs?.map(({ lang: l, url }) => (
    <link rel="alternate" hreflang={l} href={url} />
  ))}
  {hreflangPairs && (
    <link rel="alternate" hreflang="x-default"
      href={hreflangPairs.find((p) => p.lang === DEFAULT_LANG)?.url ?? '/'} />
  )}
</head>
```

## Page-Level Usage

### Landing Page
```astro
---
import { LANGUAGES, DEFAULT_LANG } from '../i18n/index.js';

const hreflangPairs = Object.keys(LANGUAGES).map((l) => ({
  lang: l,
  url: l === DEFAULT_LANG
    ? `${import.meta.env.SITE}/`
    : `${import.meta.env.SITE}/${l}/`,
}));
---
<Layout
  lang="en"
  title={t.seoHomeTitle}
  description={t.seoHomeDescription}
  canonical={`${import.meta.env.SITE}/`}
  type="website"
  jsonLd={jsonLd}
  hreflangPairs={hreflangPairs}
/>
```

### Blog Post
```astro
<Layout
  lang={lang}
  title={`${title} | Blog`}
  description={description}
  canonical={canonical}
  ogImage={ogImage}
  type="article"
  jsonLd={jsonLd}
  publishedTime={date.toISOString()}
  articleTags={tags}
  hreflangPairs={hreflangPairs}
/>
```

### Admin/Protected Page
```astro
<Layout title="Admin" noindex />
```

## og:locale Mapping

Map 2-letter lang codes to full Open Graph locales:

```javascript
const ogLocaleMap = {
  en: 'en_US',
  zh: 'zh_CN',
  ja: 'ja_JP',
  de: 'de_DE',
  fr: 'fr_FR',
};
const ogLocale = ogLocaleMap[lang] || 'en_US';
```

## Canonical URL Strategy

- Default locale: `{SITE}/blog/slug/`
- Non-default locale: `{SITE}/zh/blog/slug/`
- Each locale has its own canonical (self-referencing)
- `x-default` hreflang always points to the default locale version

## Title Fallback

Layout provides a default title from translations if not passed:

```javascript
const resolvedTitle = title ?? t.seoHomeTitle;
const resolvedDescription = description ?? t.seoHomeDescription;
```

Blog posts override with `${post.title} | ${t.blogLayoutTitleSuffix}`.
