# Google Analytics 4 Integration

## GA4 Tag Setup

Inject GA4 script conditionally in Layout.astro:

```astro
---
const gaId = import.meta.env.PUBLIC_GA_ID;
---

{gaId && (
  <>
    <script async src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}></script>
    <script is:inline define:vars={{ gaId }}>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', gaId);
    </script>
  </>
)}
```

**Key:** Uses `is:inline` + `define:vars` to pass the env var into a client-side script without Astro processing it. No GA tag in dev if `PUBLIC_GA_ID` is not set.

## Custom Event Tracking

### Download Click
```javascript
if (typeof window.gtag === 'function') {
  window.gtag('event', 'download_click', {
    button_location: 'hero',  // or 'pricing', 'nav'
    lang: currentLang,
  });
}
```

### Checkout Open
```javascript
window.gtag('event', 'checkout_open', {
  lang: currentLang,
  price_id: import.meta.env.PUBLIC_PRICE_ID,  // Your payment provider's price ID
});
```

### Purchase Complete
```javascript
window.gtag('event', 'purchase', {
  transaction_id: txnId,
  value: parseFloat(event.data?.totals?.total) || 0,
  currency: event.data?.currency_code || 'USD',
  items: [{
    item_id: priceId,
    item_name: 'YourApp',
    price: parseFloat(event.data?.totals?.total) || 0,
    quantity: 1,
  }],
  lang: currentLang,
  event_callback: () => navigateToSuccessPage(),
});
// Fallback timeout if GA is blocked or slow
setTimeout(navigateToSuccessPage, 1000);
```

## Best Practices

- Always check `typeof window.gtag === 'function'` before calling (GA may be blocked)
- Use `event_callback` for navigation-after-tracking, with a `setTimeout` fallback
- Include `lang` in all custom events for locale-based analysis
- Use `button_location` parameter to track which CTA drives conversions
- GA4 automatically tracks pageviews via `gtag('config', gaId)` — no manual pageview events needed

## Environment Variable

```
PUBLIC_GA_ID=G-XXXXXXXXXX   # GA4 Measurement ID
```

This is a public (client-exposed) variable — safe to commit in `.env`.
