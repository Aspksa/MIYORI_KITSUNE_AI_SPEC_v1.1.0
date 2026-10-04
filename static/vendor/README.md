# Local offline UI libraries

* Marked 8.0.0: `static/vendor/marked.umd.js`, MIT License, https://github.com/markedjs/marked (pinned v8.0.0).
* DOMPurify 3.2.6: `static/vendor/purify.min.js`, dual Apache-2.0 / MPL-2.0 License, https://github.com/cure53/DOMPurify (pinned 3.2.6).
* Input is rendered only when both libraries are available. Otherwise messages fall back to text-only escaped output. The DOMPurify allowlist excludes images, iframes, scripts and arbitrary HTML attributes. No remote assets or CDN are loaded.
* Header/composer icons are embedded inline SVG inspired by Lucide (ISC), see https://lucide.dev/license.
