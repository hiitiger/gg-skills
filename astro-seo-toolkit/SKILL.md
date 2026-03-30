---
name: astro-seo-toolkit
description: "Comprehensive SEO setup for Astro sites: JSON-LD structured data, Open Graph, Twitter Cards, hreflang, canonical URLs, sitemap, Google Analytics, robots.txt, and llms.txt. Use when: (1) adding SEO meta tags to Astro layouts, (2) implementing JSON-LD structured data (Organization, SoftwareApplication, FAQPage, BlogPosting, BreadcrumbList), (3) setting up Open Graph and Twitter Card meta, (4) configuring hreflang for multilingual sites, (5) generating XML sitemaps with @astrojs/sitemap, (6) adding Google Analytics 4 tracking with custom events, (7) creating canonical URL strategy for multi-locale pages, (8) configuring robots.txt with AI crawler rules, (9) creating llms.txt for LLM discoverability."
---

# Astro SEO Toolkit

Complete SEO implementation patterns for Astro sites, covering structured data, meta tags, sitemaps, and analytics. All SEO is handled in `Layout.astro` — individual pages pass SEO data as props.

## Layout Props Interface

```typescript
interface Props {
  lang?: string;
  title?: string;
  description?: string;
  canonical?: string;
  ogImage?: string;
  type?: 'website' | 'article';
  jsonLd?: object;
  hreflangPairs?: Array<{ lang: string; url: string }>;
  noindex?: boolean;
  publishedTime?: string;
  articleTags?: string[];
}
```

All SEO concerns flow through this single interface. Pages set these props; `Layout.astro` renders them.

## JSON-LD Structured Data

See [references/json-ld-schemas.md](references/json-ld-schemas.md) for all schema templates.

**Rendering pattern** — pass JSON-LD as prop, render in `<head>` (see [references/json-ld-schemas.md](references/json-ld-schemas.md) for rendering code and all schema templates):

**Available schemas:**
- `Organization` — always rendered (site-wide brand identity)
- `SoftwareApplication` — home/landing page (product info + pricing)
- `FAQPage` — pages with FAQ sections (question/answer pairs)
- `BlogPosting` — individual blog posts (headline, date, author)
- `BreadcrumbList` — blog posts (navigation hierarchy)

Pages can pass arrays of schemas as `jsonLd` prop.

## Meta Tags

See [references/meta-tags.md](references/meta-tags.md) for complete implementation.

**Covers:**
- Primary meta (title, description, canonical)
- Open Graph (type, title, description, image, locale, URL)
- Twitter Cards (summary_large_image, site handle)
- Article meta (published_time, modified_time, tags)
- Robots (noindex for admin/protected pages)
- Hreflang with `x-default`

## Sitemap

Auto-generated via `@astrojs/sitemap`:

```javascript
// astro.config.mjs
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://yourdomain.com',
  integrations: [sitemap()],
});
```

No manual configuration needed — all static pages are included automatically. Set `noindex` on pages that should be excluded (admin, success, etc.).

## Crawl Control & LLM Discoverability

See [references/crawl-and-llms.md](references/crawl-and-llms.md) for complete implementation.

**Covers:**
- `robots.txt` — default allow-all with explicit AI crawler rules (GPTBot, ClaudeBot, PerplexityBot, etc.)
- `llms.txt` — machine-readable product summary for LLM discoverability (llmstxt.org standard)
- When to disallow routes (API endpoints, staging)
- Optional `llms-full.txt` for products with extensive documentation

## Google Analytics 4

See [references/analytics.md](references/analytics.md) for implementation.

**Covers:**
- GA4 tag injection (conditional on `PUBLIC_GA_ID` env var)
- Custom event tracking: `download_click`, `checkout_open`, `purchase`
- Event parameters: `button_location`, `lang`, `price_id`, `transaction_id`
- `event_callback` for navigation after purchase event

## Checklist

- [ ] `<html lang>` set to page locale
- [ ] `<title>` and `<meta name="description">` on every page
- [ ] Canonical URL on every page (locale-specific)
- [ ] Open Graph tags: type, title, description, image, locale, url
- [ ] Twitter Card: summary_large_image with site handle
- [ ] hreflang tags for all supported locales + x-default
- [ ] JSON-LD Organization schema on every page
- [ ] JSON-LD contextual schemas (SoftwareApplication, BlogPosting, etc.)
- [ ] Sitemap via @astrojs/sitemap integration
- [ ] `noindex` on non-public pages (admin, success, etc.)
- [ ] GA4 tag conditional on env var (no tracking in dev)
- [ ] Article meta (published_time, tags) on blog posts
- [ ] `robots.txt` with AI crawler rules and sitemap reference
- [ ] `llms.txt` with product summary, features, and blog links
- [ ] API routes disallowed in robots.txt if applicable
