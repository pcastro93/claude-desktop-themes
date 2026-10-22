# AGENTS.md

Custom themes for the Claude Desktop app (Electron), applied as CSS variable overrides from a DevTools snippet.

## Layout
- `css-dump/`: the app's CSS and the tools that process it. `all.css`, `vars.css` and `vars.colors.css` are git-ignored (they're the app's own CSS), so on a fresh clone create them first; see [How to create the CSS dumps](#how-to-create-the-css-dumps).
  - `VERSION`: the Claude Desktop version the dumps came from.
  - `all.css`: full stylesheet dump (2.4 MB, ~850k tokens). **Never read it in full**; use `rg`.
  - `vars.colors.css`: color variables only (~40k tokens). Input for the generator. Avoid reading it in full.
  - `vars.css`: all CSS variables, including fonts and spacing (~160k tokens).
  - `dump-css.js`: DevTools snippet that produces `all.css`.
  - `extract_vars.py`: builds the `vars*.css` files from `all.css`.
- `generator/`: the theme builder.
  - `generate.py`: builds `theme.css` + `apply-theme.js` from a `palette.toml`, writing them next to it.
  - `PALETTE.md`: every palette key.
- `themes/<name>/`: one folder per theme. `palette.toml` is the source; `theme.css` and `apply-theme.js` are generated, so don't edit them by hand.

## How to create the CSS dumps
1. **`all.css`:**
   - Open DevTools in Claude Desktop (see [Setup](README.md#setup)) and run `css-dump/dump-css.js` in the Console.
   - It concatenates every stylesheet on the page (`document.styleSheets` + `adoptedStyleSheets`) and fetches cross-origin sheets.
   - The result downloads as `all.css`; move it to `css-dump/`.
2. **`vars.css`:** run `uv run extract_vars.py all.css -o vars.css` in `css-dump/`.
   - It keeps only `--*` custom properties, with their selectors and `@media`/`@layer` wrappers.
   - It drops Tailwind's internal `--tw-*` variables and removes duplicate rules.
3. **`vars.colors.css`:** same command plus `--colors-only`, which keeps values that look like colors (hex, `rgb()`, `hsl()`, `oklch()`, `color-mix()`, bare `H S% L%` triplets).

Redo all three after an app update (the CSS file names are hashed and change), write the new version (from the app's About dialog) to `css-dump/VERSION`, then regenerate the themes.

## Commands
Use `uv`, never pip.
```bash
uv run generator/generate.py themes/<name>/palette.toml                          # build a theme
cd css-dump && uv run extract_vars.py all.css --colors-only -o vars.colors.css  # refresh after the app updates
```

## How themes are applied
- Paste `apply-theme.js` into DevTools → Sources → Snippets and run it with Ctrl+Enter (Cmd+Enter on macOS). It upserts `<style id="custom-theme">`.
- Undo with `document.getElementById('custom-theme').remove()`.
- **Dead ends:**
  - The app refuses to start with `--remote-debugging-port`.
  - Its Electron fuses enforce asar integrity, so editing `app.asar` is blocked too.
  - DevTools Local Overrides of the app's CSS broke the inline code styling.
  - No startup hook: no custom-CSS setting, snippets can't auto-run, and `--inspect`/`NODE_OPTIONS` are disabled by fuses.

## Conventions
- **Override strategy:** one unlayered rule, `:root, :root *, :root ::before, :root ::after { --x: v !important; }`. It beats the app's per-element redeclarations.
- **Value formats:** keep each variable's original format (hex, 8-digit hex, bare `H S% L%` triplets, `rgb()`), or the color breaks.
- **`--cds-neutral-900`** is the base of every `--cds-alpha-*` overlay. Keep it pinned to `fg_strong`.
- **Verify after changes:**
  - Each `theme.css` parses with 0 errors (tinycss2). Every declaration is `!important`, and all are custom properties except the `font-size` in the code fallback rule that `code_font_size` adds.
  - `node --check` passes on each `apply-theme.js`, and its embedded string equals `theme.css`.
  - All themes still generate.
