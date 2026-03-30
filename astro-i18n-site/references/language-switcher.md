# Language Switcher & Detection

## Language Switcher (React Component)

### Path Rewriting Logic

The switcher must rewrite the current path to the target language, preserving the rest of the path:

```javascript
function getLangSwitchPath(currentPath, targetLang) {
  // Strip existing non-default lang prefix (e.g. /zh/blog/foo → /blog/foo)
  const nonDefaultPrefixMatch = currentPath.match(/^\/([a-z]{2})(\/.*)?$/);
  const isNonDefault =
    nonDefaultPrefixMatch &&
    nonDefaultPrefixMatch[1] in LANGUAGES &&
    nonDefaultPrefixMatch[1] !== DEFAULT_LANG;
  const rest = isNonDefault ? nonDefaultPrefixMatch[2] || '/' : currentPath;
  // Prepend target lang (or bare path for default)
  return targetLang === DEFAULT_LANG ? rest : `/${targetLang}${rest}`;
}
```

**Examples** (assuming `DEFAULT_LANG = 'en'`):
- `/zh/blog/foo` + target `en` → `/blog/foo`
- `/blog/foo` + target `zh` → `/zh/blog/foo`
- `/zh/` + target `ja` → `/ja/`
- `/` + target `zh` → `/zh/`

### Dropdown Component

```jsx
const LanguageSwitcher = ({ lang, currentPath }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)}>
        <Globe /> {LANGUAGES[lang].label} <ChevronDown />
      </button>
      {open && (
        <div className="absolute right-0 mt-1.5 w-36 bg-white border rounded-xl shadow-lg">
          {Object.entries(LANGUAGES).map(([code, { name }]) => (
            <a
              key={code}
              href={getLangSwitchPath(currentPath, code)}
              onClick={() => {
                try { localStorage.setItem('preferred-lang', code); } catch {}
              }}
              className={code === lang ? 'font-semibold text-cyan-600' : 'text-slate-600'}
            >
              {name}
            </a>
          ))}
        </div>
      )}
    </div>
  );
};
```

### Navbar Integration

Pass `lang` and `currentPath` from Astro layout:

```astro
<!-- In Layout.astro -->
<Navbar client:load lang={lang} currentPath={Astro.url.pathname} />
```

Navigation links use locale-aware base path:

```javascript
const home = getLocalePath(lang); // "/" or "/zh/"
const navLinks = [
  { href: `${home}#features`, label: t.navFeatures },
  { href: `${home}#pricing`, label: t.navPricing },
  { href: lang === 'en' ? '/blog/' : `/${lang}/blog/`, label: t.navBlog },
];
```

## Language Detection Banner

Suggests switching language based on browser preference:

```jsx
const DISMISS_KEY = 'lang-banner-dismissed';

function detectTargetLang(currentLang) {
  try {
    if (localStorage.getItem('preferred-lang')) return null;  // Already chose
    if (localStorage.getItem(DISMISS_KEY)) return null;       // Dismissed
  } catch { return null; }

  const browserLangs = navigator.languages || [navigator.language];
  for (const bl of browserLangs) {
    const code = bl.split('-')[0].toLowerCase();
    if (code in LANGUAGES && code !== currentLang) return code;
  }
  return null;
}

const LanguageBanner = ({ lang, currentPath }) => {
  const [targetLang, setTargetLang] = useState(null);

  useEffect(() => {
    const matched = detectTargetLang(lang);
    if (matched) setTargetLang(matched);
  }, [lang]);

  if (!targetLang) return null;

  const t = getTranslation(targetLang);  // Show message in TARGET language
  const switchPath = getLangSwitchPath(currentPath, targetLang);

  return (
    <div className="fixed top-16 left-0 right-0 z-40 bg-cyan-50 border-b">
      <p>{t.langBannerMessage}</p>
      <a href={switchPath} onClick={() => {
        localStorage.setItem('preferred-lang', targetLang);
      }}>
        {t.langBannerSwitch}
      </a>
      <button onClick={() => {
        localStorage.setItem(DISMISS_KEY, '1');
        setTargetLang(null);
      }}>
        <X />
      </button>
    </div>
  );
};
```

**Key details:**
- Banner message uses the **target** language's translations (not current page lang)
- Positioned below fixed navbar (`top-16`)
- Three dismissal states: user chose a language, banner dismissed, or no match
- `useEffect` ensures SSR-safe (detection runs client-side only)

> **Client-side `getTranslation` note:** Both `LanguageBanner` and `Navbar` import `getTranslation` from `../i18n/index.js`. Because Astro uses Vite, JSON imports are bundled automatically — the translation files are inlined into the client bundle. No extra configuration is needed, but be aware this increases bundle size if translation files are large. For large translation files, consider fetching translations via props from the Astro parent instead.

## Landing Page Auto-Redirect

Separate from the banner — an inline script in `Layout.astro` that redirects returning users:

```html
<script is:inline>
(function () {
  if (window.location.pathname !== '/') return;  // Only on root landing
  var lang = localStorage.getItem('preferred-lang');
  if (lang && lang !== DEFAULT_LANG) {
    window.location.replace('/' + lang + '/');
  }
})();
</script>
```

This runs before React hydration for instant redirect. Only affects the root path — deep links (blog posts, etc.) are not redirected.

> **Note:** The `DEFAULT_LANG` value must be inlined since this is an `is:inline` script without bundler access. Replace `'en'` with your actual default locale if different.
