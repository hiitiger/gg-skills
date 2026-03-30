# Multilingual Blog with Content Collections

## Content Collection Schema

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    tags: z.array(z.string()),  // Use z.enum([...]) to restrict to known tags
    ogImage: z.string().optional(),
  }),
});

export const collections = { blog };
```

## Content Organization

```
src/content/blog/
├── en/
│   ├── how-to-monitor-processes.md
│   └── understanding-process-tree.md
├── zh/
│   ├── how-to-monitor-processes.md     # Same slug = same article
│   └── understanding-process-tree.md
├── ja/
│   └── how-to-monitor-processes.md
└── ...
```

Same slug across languages enables automatic hreflang pairing.

## Default Locale Blog Index

```astro
---
// src/pages/blog/index.astro
import { getCollection } from 'astro:content';
import Layout from '../../layouts/Layout.astro';
import { LANGUAGES, DEFAULT_LANG, getTranslation } from '../../i18n/index.js';

const t = getTranslation('en');

const posts = (
  await getCollection('blog', ({ id }) => id.startsWith('en/'))
).sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());

const formattedPosts = posts.map((post) => ({
  ...post,
  slug: post.id.replace('en/', '').replace(/\.md$/, ''),
  formattedDate: new Intl.DateTimeFormat('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  }).format(post.data.date),
}));
---

<Layout lang="en" title={t.blogIndexTitle}
  canonical={`${import.meta.env.SITE}/blog/`}
  hreflangPairs={Object.keys(LANGUAGES).map((l) => ({
    lang: l,
    url: l === DEFAULT_LANG
      ? `${import.meta.env.SITE}/blog/`
      : `${import.meta.env.SITE}/${l}/blog/`,
  }))}
>
  {formattedPosts.map((post) => (
    <a href={`/blog/${post.slug}`}>
      <h2>{post.data.title}</h2>
      <time datetime={post.data.date.toISOString()}>{post.formattedDate}</time>
    </a>
  ))}
</Layout>
```

## Default Locale Blog Post

```astro
---
// src/pages/blog/[slug].astro
import { getCollection, render } from 'astro:content';
import BlogLayout from '../../layouts/BlogLayout.astro';

export async function getStaticPaths() {
  const posts = await getCollection('blog', ({ id }) => id.startsWith('en/'));
  return posts.map((post) => {
    const slug = post.id.replace('en/', '').replace(/\.md$/, '');
    return { params: { slug }, props: { post } };
  });
}

const { post } = Astro.props;
const { Content } = await render(post);
const slug = post.id.replace('en/', '').replace(/\.md$/, '');
---

<BlogLayout lang="en" title={post.data.title} description={post.data.description}
  date={post.data.date} tags={post.data.tags} slug={slug}>
  <Content />
</BlogLayout>
```

## Non-Default Locale Blog Index

```astro
---
// src/pages/[lang]/blog/index.astro
import { getCollection } from 'astro:content';
import { LANGUAGES, DEFAULT_LANG, getTranslation } from '../../../i18n/index.js';

export async function getStaticPaths() {
  return Object.keys(LANGUAGES)
    .filter((lang) => lang !== DEFAULT_LANG)
    .map((lang) => ({ params: { lang } }));
}

const { lang } = Astro.params;
const t = getTranslation(lang);

const posts = (
  await getCollection('blog', ({ id }) => id.startsWith(`${lang}/`))
).sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf());

const formattedPosts = posts.map((post) => ({
  ...post,
  slug: post.id.replace(`${lang}/`, '').replace(/\.md$/, ''),
  formattedDate: new Intl.DateTimeFormat(lang, {
    year: 'numeric', month: 'long', day: 'numeric',
  }).format(post.data.date),
}));
---
<!-- Link pattern: /{lang}/blog/{slug} -->
```

## Non-Default Locale Blog Post (Nested Dynamic)

```astro
---
// src/pages/[lang]/blog/[slug].astro
import { getCollection, render } from 'astro:content';
import BlogLayout from '../../../layouts/BlogLayout.astro';
import { LANGUAGES, DEFAULT_LANG } from '../../../i18n/index.js';

export async function getStaticPaths() {
  const nonDefaultLangs = Object.keys(LANGUAGES).filter((l) => l !== DEFAULT_LANG);
  const paths = [];

  for (const lang of nonDefaultLangs) {
    const posts = await getCollection('blog', ({ id }) => id.startsWith(`${lang}/`));
    for (const post of posts) {
      const slug = post.id.replace(`${lang}/`, '').replace(/\.md$/, '');
      paths.push({ params: { lang, slug }, props: { post, lang } });
    }
  }

  return paths;
}

const { post, lang } = Astro.props;
const { Content } = await render(post);
const slug = post.id.replace(`${lang}/`, '').replace(/\.md$/, '');
---

<BlogLayout lang={lang} title={post.data.title} description={post.data.description}
  date={post.data.date} tags={post.data.tags} slug={slug}>
  <Content />
</BlogLayout>
```

## BlogLayout Patterns

The `BlogLayout.astro` wraps `Layout.astro` and adds:

1. **Locale-aware URLs** — build all hreflang URLs dynamically from the slug:
   ```javascript
   const hreflangPairs = Object.keys(LANGUAGES).map((l) => ({
     lang: l,
     url: l === DEFAULT_LANG
       ? `${import.meta.env.SITE}/blog/${slug}/`
       : `${import.meta.env.SITE}/${l}/blog/${slug}/`,
   }));
   ```

2. **Locale-aware date formatting:**
   ```javascript
   const localeMap = { en: 'en-US', zh: 'zh-CN', ja: 'ja-JP', de: 'de-DE', fr: 'fr-FR' };
   const formattedDate = new Intl.DateTimeFormat(localeMap[lang] || lang, {
     year: 'numeric', month: 'long', day: 'numeric',
   }).format(date);
   ```

3. **JSON-LD structured data** — `BlogPosting` + `BreadcrumbList` with `inLanguage` set per locale

4. **Article meta** — `publishedTime`, `articleTags` passed to Layout for Open Graph

5. **Prose styling** — `@tailwindcss/typography` with customized Tailwind classes

6. **Social share links** — Twitter, LinkedIn, Telegram + copy-to-clipboard using canonical URL
