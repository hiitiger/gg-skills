# JSON-LD Structured Data Schemas

## Rendering Pattern

Pass schemas as `jsonLd` prop to Layout. Can be a single object or array:

```astro
<!-- In Layout.astro <head> -->
{jsonLd && (
  <script type="application/ld+json" set:html={JSON.stringify(jsonLd)} />
)}
<!-- Organization always present -->
<script type="application/ld+json" set:html={JSON.stringify(organizationLd)} />
```

## Organization (Site-Wide)

Always rendered on every page — defines the brand:

```javascript
const organizationLd = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'YourApp',
  url: import.meta.env.SITE,
  logo: `${import.meta.env.SITE}/og-default.png`,
  description: 'Your app description.',
};
```

## SoftwareApplication (Landing Page)

For software product pages with pricing:

```javascript
{
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'YourApp',
  operatingSystem: 'macOS',
  applicationCategory: 'DeveloperApplication',
  offers: {
    '@type': 'Offer',
    price: '15',
    priceCurrency: 'USD',
  },
  description: t.seoHomeJsonLdDescription,
  url: import.meta.env.SITE,
}
```

## FAQPage (Landing Page)

For pages with FAQ sections — use translation keys for Q&A:

```javascript
{
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: [
    {
      '@type': 'Question',
      name: t.faq1Q,
      acceptedAnswer: { '@type': 'Answer', text: t.faq1A },
    },
    {
      '@type': 'Question',
      name: t.faq2Q,
      acceptedAnswer: { '@type': 'Answer', text: t.faq2A },
    },
    // ... more Q&A pairs
  ],
}
```

Pages can pass both SoftwareApplication and FAQPage as an array:
```javascript
const jsonLd = [softwareAppLd, faqLd];
```

## BlogPosting (Blog Post Detail)

For individual blog articles:

```javascript
{
  '@context': 'https://schema.org',
  '@type': 'BlogPosting',
  headline: title,
  description: description,
  datePublished: date.toISOString(),
  dateModified: date.toISOString(),
  inLanguage: ({ en: 'en-US', zh: 'zh-CN', ja: 'ja-JP', de: 'de-DE', fr: 'fr-FR' })[lang] || lang,
  mainEntityOfPage: {
    '@type': 'WebPage',
    '@id': canonical,
  },
  image: ogImage ?? `${import.meta.env.SITE}/og-default.png`,
  author: {
    '@type': 'Organization',
    name: 'YourApp',
    url: import.meta.env.SITE,
  },
  publisher: {
    '@type': 'Organization',
    name: 'YourApp',
    url: import.meta.env.SITE,
  },
}
```

**Key:** Set `inLanguage` to the proper BCP 47 locale (e.g., `zh-CN`, `en-US`, `ja-JP`).

## BreadcrumbList (Blog Post Detail)

Navigation hierarchy for blog posts — paired with BlogPosting:

```javascript
{
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'Home', item: homeUrl },
    { '@type': 'ListItem', position: 2, name: 'Blog', item: blogIndexUrl },
    { '@type': 'ListItem', position: 3, name: title, item: canonical },
  ],
}
```

Use localized labels from translation keys (e.g., `t.blogBreadcrumbHome`).

## Multilingual Considerations

- `SoftwareApplication.url` should be locale-specific (e.g., `{SITE}/zh/`)
- `BlogPosting.inLanguage` maps lang code to BCP 47 format
- BreadcrumbList labels and URLs must use locale-aware paths
- FAQ Q&A content comes from translation keys (auto-localized)
