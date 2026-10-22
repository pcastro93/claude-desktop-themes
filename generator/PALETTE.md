# Palette format

Palette-driven CSS variable overrides for the Claude Desktop app.

## Add a theme
1. `cp -r themes/solarized-dark themes/mytheme` and edit `themes/mytheme/palette.toml`.
2. `uv run generator/generate.py themes/mytheme/palette.toml` (optional `--vars path/to/vars.colors.css`, default `../css-dump/vars.colors.css`).
   This writes `theme.css` and `apply-theme.js` next to the palette and prints per-group declaration counts.
3. Open DevTools, paste `apply-theme.js` into Sources > Snippets, run with Ctrl+Enter (Cmd+Enter on macOS).
4. Undo: `document.getElementById('custom-theme').remove()`.

Re-running the snippet replaces the previous theme (same `<style id="custom-theme">`).

## Palette keys
Colors are `"#rrggbb"`. Role picks accept a hue name, a ramp key or a hex.

| Key | Meaning |
|---|---|
| `name`, `mode` | Display name (used in the snippet log); `"light"` or `"dark"` |
| `bg` | Page / main surface |
| `bg_alt` | Sidebar, secondary surfaces |
| `border`, `border_strong` | Solid border / divider steps (also `--bg-300`, `--bg-400/500`) |
| `fg_subtle` | Disabled / faintest text |
| `fg_muted` | Muted text |
| `fg_secondary` | Secondary text |
| `fg` | Primary text |
| `fg_strong` | Headings, strongest text; base of translucent borders, fills and overlays |
| `ink` | Extreme end of the ramp (darkest in light mode, lightest in dark mode); hover/text hue variants are mixed toward it |
| `on_color` | Text on saturated fills (accent, danger, success, warning, pro, brand) |
| `hues` | Inline table with `red orange yellow green aqua blue violet magenta`; drives the hue scales and tints |
| `accent` | Links, focus, accent buttons |
| `brand` | Brand/"clay" color |
| `pro` | Pro-plan color |
| `success`, `warning`, `danger` | Status colors |
| `primary_button` / `primary_button_hover` | Primary button fill and hover (default hover `fg`) |
| `on_primary` | Text on the primary button (default `bg`) |
| `shadow` | Optional shadow/backdrop base color (default `fg_strong` in light, darkened `bg` in dark) |
| `hue_hover`, `hue_text` | Optional inline tables with exact hover-fill / readable-text colors per hue (default: derived by mixing toward `ink`) |
| `override` | Optional inline table `"--css-var" = value` for exact per-variable values (hex is auto-converted for `H S% L%` variables) |
| `code_font_size` | Optional code font size, e.g. `"13.5px"` (bare numbers mean px). Sets `--cds-font-size-code`, `--msg-code-font-size`, `--prompt-text-code` and adds a `pre, pre code, .code-block__code` fallback rule |
| `code_line_height` | Optional unitless code line height, used only with `code_font_size` (default `1.5`) |

Ramp order is by contrast: `bg < bg_alt < border < border_strong < fg_subtle < fg_muted < fg_secondary < fg < fg_strong < ink`.
In a dark theme that means dark to light.

## How dark mode works
The app's original gray scale is mapped through the ramp by lightness, so originally light grays become `bg` and
originally dark grays become `fg_strong`/`ink`; no extra setting needed. Hue scales have their lightness flipped in dark
mode (low steps become dark tints). Translucent borders and fills use `fg_strong` as base, shadows use `shadow` at
double strength, and `on_primary` is `bg`.
