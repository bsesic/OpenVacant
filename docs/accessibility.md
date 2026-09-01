# Accessibility (WCAG) checklist

Accessibility is a process, not a dependency. Run an automated audit and fix findings
before each release.

## Run an audit

- **Lighthouse**: Chrome DevTools → Lighthouse → Accessibility (or `npx lighthouse <url> --only-categories=accessibility`).
- **axe**: the [axe DevTools](https://www.deque.com/axe/devtools/) browser extension, or `@axe-core/cli`.

## Baseline the boilerplate already provides

- `lang` attribute on `<html>` (driven by the active language).
- Semantic landmarks: `<nav>`, `<main>`, `<footer>`.
- Labelled controls (crispy-forms renders `<label>`s; the language switcher and icon
  buttons have `aria-label`s).
- Bootstrap 5 components with built-in ARIA (navbar toggler, dropdowns, accordion).

## Per-project checklist

- [ ] Color contrast ≥ 4.5:1 for text (check your brand colors in `main.scss`).
- [ ] All images have meaningful `alt` text (decorative images use `alt=""`).
- [ ] Every form field has a visible label and error messages are associated.
- [ ] Keyboard navigation works end to end; visible focus styles are present.
- [ ] Headings are hierarchical (one `<h1>` per page).
- [ ] Interactive icons/buttons have accessible names.
- [ ] Run Lighthouse/axe on the main flows and fix issues before release.
