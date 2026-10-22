#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate theme.css + apply-theme.js for Claude Desktop from a palette.toml.

Usage: uv run generator/generate.py themes/<name>/palette.toml [--vars path/to/vars.colors.css]
See generator/PALETTE.md for the palette format.
"""
import re, sys, json, colorsys, collections, argparse, tomllib, pathlib

ap = argparse.ArgumentParser()
ap.add_argument('palette')
ap.add_argument('--vars', default=None, help='vars.colors.css (default: ../css-dump/vars.colors.css)')
args = ap.parse_args()
pal_path = pathlib.Path(args.palette).resolve()
vars_path = pathlib.Path(args.vars) if args.vars else pathlib.Path(__file__).resolve().parent.parent / 'css-dump' / 'vars.colors.css'
if not vars_path.is_file():  # git-ignored, so missing on a fresh clone
    sys.exit(f'{vars_path} not found: create it first (AGENTS.md, "How to create the CSS dumps").')
SRC = vars_path.read_text().split('\n')
P = tomllib.loads(pal_path.read_text())
NAME, MODE = P['name'], P['mode']

# A hex color without its leading '#' would be copied into the CSS as-is and silently break that variable.
_values = [(k, v) for k, v in P.items() if isinstance(v, str)]
_values += [(f'{t}.{k}', v) for t in ('hues', 'hue_hover', 'hue_text') for k, v in P.get(t, {}).items()]
_bad = [f'{k} = "{v}"' for k, v in _values if re.fullmatch(r'[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8}', v)]
if _bad:
    sys.exit(f'{pal_path}: hex colors need a leading "#": ' + ', '.join(_bad))
assert MODE in ('light', 'dark'), 'mode must be "light" or "dark"'
DARK = MODE == 'dark'

# ---- colour helpers --------------------------------------------------------
def h2r(h):
    h = h.lstrip('#')
    if len(h) == 3: h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def r2h(c): return '#%02x%02x%02x' % tuple(max(0, min(255, round(x))) for x in c)
def mix(a, b, t):  # t of b
    A, B = h2r(a), h2r(b); return r2h([x + (y - x) * t for x, y in zip(A, B)])
def alpha(h, pct): return h + '%02x' % round(min(100, pct) * 255 / 100)
def hsl_of(h):
    r, g, b = [x / 255 for x in h2r(h)]; hh, l, s = colorsys.rgb_to_hls(r, g, b); return hh * 360, s * 100, l * 100
def trip(h):
    a, b, c = hsl_of(h); return f'{a:.1f} {b:.1f}% {c:.1f}%'
def rgb_fn(h, a=1): r, g, b = h2r(h); return f'rgb({r} {g} {b} / {a})'

# ---- palette ---------------------------------------------------------------
RAMP = ['bg', 'bg_alt', 'border', 'border_strong', 'fg_subtle', 'fg_muted', 'fg_secondary', 'fg', 'fg_strong', 'ink']
R = {k: P[k].lower() for k in RAMP}
HUE_NAMES = ['red', 'orange', 'yellow', 'green', 'aqua', 'blue', 'violet', 'magenta']
HUES = {k: P['hues'][k].lower() for k in HUE_NAMES}
HOVER = {k: v.lower() for k, v in P.get('hue_hover', {}).items()}
TEXT = {k: v.lower() for k, v in P.get('hue_text', {}).items()}
OVERRIDE = P.get('override', {})
ON_COLOR = P['on_color'].lower()

def resolve(tok):
    tok = tok.strip()
    if tok in R: return R[tok]
    if tok in HUES: return HUES[tok]
    return tok.lower()
def hover(tok):  # fill hover colour for a hue name / ramp name / hex
    if tok in HOVER: return HOVER[tok]
    return mix(resolve(tok), R['ink'], 0.10)
def text(tok):   # readable text colour of a hue; towards ink = darker (light) or lighter (dark)
    if tok in TEXT: return TEXT[tok]
    return mix(resolve(tok), R['ink'], 0.22)

ACCENT, BRAND, PRO = P['accent'], P['brand'], P['pro']
SUCCESS, WARNING, DANGER = P['success'], P['warning'], P['danger']
PRIMARY = resolve(P['primary_button'])
PRIMARY_H = resolve(P.get('primary_button_hover', 'fg'))
ON_PRIMARY = resolve(P.get('on_primary', 'bg'))
SHADOW = resolve(P['shadow']) if 'shadow' in P else (mix(R['bg'], '#000000', .5) if DARK else R['fg_strong'])
SH = 2.0 if DARK else 1.0   # shadow / backdrop strength
OV = R['fg_strong']         # base for translucent neutral fills and borders (light base on dark themes)
BG, ALT, INK = R['bg'], R['bg_alt'], R['ink']
LIGHTEST, DARKEST = (INK, BG) if DARK else (BG, INK)

# ---- parse originals -------------------------------------------------------
orig_hex, orig_trip = {}, {}
for ln in SRC[194:462]:
    m = re.match(r'\s*(--cds-(?:gray|red|orange|yellow|green|aqua|blue|violet|magenta)-\d+): (#[0-9a-f]{3,6});', ln)
    if m: orig_hex[m[1]] = m[2]
for ln in SRC[75:131] + SRC[837:895]:
    m = re.match(r'\s*(--cds-hsl-[a-z]+-\d+): ([\d.]+) ([\d.]+)% ([\d.]+)%;', ln)
    if m: orig_trip[m[1]] = tuple(map(float, m.groups()[1:]))
assert orig_hex and orig_trip, 'could not parse scales from vars file (line ranges changed?)'
def full(h):
    h = h.lstrip('#'); return '#' + (''.join(c * 2 for c in h) if len(h) == 3 else h)

# Original gray lightness (0..255) -> palette neutral. Same role order in light and dark: original light grays land on
# the page background and original dark grays on the strongest foreground, so dark palettes flip automatically.
GRAY_STOPS = [(252, R['bg']), (224, R['bg_alt']), (135, R['fg_subtle']), (107, R['fg_secondary']),
              (81, R['fg']), (32, R['fg_strong']), (0, R['ink'])]
def gray_map(v):
    for (v1, c1), (v2, c2) in zip(GRAY_STOPS, GRAY_STOPS[1:]):
        if v2 <= v <= v1: return mix(c2, c1, (v - v2) / (v1 - v2))
    return R['bg'] if v > 252 else R['ink']
def hue_map(name, L):  # L 0..100 original lightness; dark mode flips it so low steps become dark tints
    if DARK: L = 100 - L
    S = HUES[name]; Ls = hsl_of(S)[2]
    if L >= Ls: return mix(S, LIGHTEST, (L - Ls) / (100 - Ls) * 0.92)
    return mix(S, DARKEST, (Ls - L) / Ls * 0.92)
def scale_name(k): return re.sub(r'^--cds-(hsl-)?', '', k).split('-')[0]
def map_hex(k, v):
    n = scale_name(k)
    return gray_map(h2r(full(v))[0]) if n == 'gray' else hue_map(n, hsl_of(full(v))[2])
def map_trip(k, h, s, l):
    n = scale_name(k)
    return trip(gray_map(l / 100 * 255)) if n == 'gray' else trip(hue_map(n, l))

groups = collections.OrderedDict()
def add(g, k, v): groups.setdefault(g, []).append((k, v))

# ---- Palette scales ----------------------------------------------------------
PH = 'Palette: hex scales (--cds-gray/red/orange/yellow/green/aqua/blue/violet/magenta-N)'
PT = 'Palette: HSL triplet scales (--cds-hsl-*)'
for k, v in orig_hex.items(): add(PH, k, map_hex(k, v))
for k, (h, s, l) in orig_trip.items(): add(PT, k, map_trip(k, h, s, l))
add(PT, '--cds-hsl-gray-0', trip(BG))
add(PH, '--cds-gray-0', BG)
g850, g860, g870, g890 = (mix(INK, R['fg_strong'], t) for t in (.10, .08, .06, .02))
add(PH, '--cds-gray-850', g850); add(PH, '--cds-gray-900', INK)
add(PT, '--cds-hsl-gray-850', trip(g850)); add(PT, '--cds-hsl-gray-900', trip(INK))
add(PT, '--cds-hsl-gray-860', trip(g860)); add(PT, '--cds-hsl-gray-870', trip(g870)); add(PT, '--cds-hsl-gray-890', trip(g890))
BRAND_C, BRAND_H = resolve(BRAND), hover(BRAND)
add(PT, '--cds-hsl-clay', trip(BRAND_C)); add(PT, '--cds-hsl-clay-emphasized', trip(BRAND_H))

# ---- Surfaces ----------------------------------------------------------------
Z3 = R['border_strong']
Z4 = mix(Z3, R['fg_subtle'], .25)
for k, v in [('--cds-surface-1', BG), ('--cds-surface-2', BG), ('--cds-surface-3', BG), ('--cds-surface-popover', BG),
             ('--cds-fizzy-lake-color-sidebar', ALT), ('--cds-fizzy-lake-color-card-hover', mix(ALT, R['border'], .5)),
             ('--cds-fill-field', alpha(BG, 50)),
             ('--df-sidebar-tint', ALT), ('--df-sidebar-bg', ALT), ('--df-web-sidebar-bg', ALT),
             ('--df-z0', trip(BG)), ('--df-z1', trip(ALT)), ('--df-z2', trip(R['border'])), ('--df-z3', trip(Z3)),
             ('--df-z4', trip(Z4)), ('--df-z5', trip(R['fg_subtle'])), ('--df-z6', trip(R['fg_secondary'])),
             ('--df-bg-page-hsl', trip(BG)),
             ('--bg-000', trip(BG)), ('--bg-100', trip(BG)), ('--bg-200', trip(ALT)), ('--bg-300', trip(R['border'])),
             ('--bg-400', trip(Z3)), ('--bg-500', trip(Z3)),
             ('--pictogram-100', trip(ALT)), ('--pictogram-200', trip(R['border'])), ('--pictogram-300', trip(BG)),
             ('--pictogram-400', trip(mix(BG, ALT, .5)))]:
    add('Surfaces', k, v)
N = 'Neutral fills / overlays'
# --cds-neutral-900 is the base of every --cds-alpha-* overlay (inline code chips, ghost hovers, skeletons).
# The app points it at --cds-gray-0 in dark mode, which this theme maps to bg, so pin it to the contrast end.
add(N, '--cds-neutral-900', OV)
for k, v in [('--cds-fill-secondary', alpha(OV, 5)), ('--cds-fill-secondary-hover', alpha(OV, 8)), ('--cds-fill-secondary-layer', alpha(OV, 2.5)),
             ('--cds-fill-ghost-hover', alpha(OV, 5)), ('--cds-fill-ghost-selected', alpha(OV, 10)),
             ('--cds-fill-button-ghost-hover', alpha(OV, 10)), ('--cds-fill-button-layer', alpha(OV, 6)),
             ('--cds-fill-disabled', alpha(OV, 2.5)), ('--cds-bg-neutral-hover', alpha(OV, 8)),
             ('--cds-fizzy-lake-color-selected-hover', alpha(OV, 14)), ('--cds-backdrop', alpha(SHADOW, 40 * SH))]:
    add(N, k, v)

# ---- Text --------------------------------------------------------------------
for k, v in [('--cds-text-primary', R['fg']), ('--cds-text-secondary', R['fg_secondary']), ('--cds-text-muted', R['fg_muted']),
             ('--cds-text-stays-secondary', R['fg_secondary']),
             ('--cds-text-button-disabled', R['fg_subtle']), ('--cds-fizzy-lake-color-tertiary', R['fg_muted']),
             ('--cds-fizzy-lake-color-secondary', R['fg_secondary']),
             ('--cds-fizzy-lake-color-plain-secondary', R['fg_secondary']), ('--cds-fizzy-lake-color-plain-muted', R['fg_secondary']),
             ('--muted-as-secondary', rgb_fn(R['fg_secondary'])),
             ('--text-000', trip(R['fg_strong'])), ('--text-100', trip(R['fg'])), ('--text-200', trip(R['fg'])),
             ('--text-300', trip(R['fg_secondary'])), ('--text-400', trip(R['fg_muted'])), ('--text-500', trip(R['fg_subtle'])),
             ('--cds-on-primary', ON_PRIMARY), ('--cds-on-accent', ON_COLOR), ('--cds-on-danger', ON_COLOR), ('--cds-on-success', ON_COLOR),
             ('--cds-on-warning', ON_COLOR), ('--cds-on-pro', ON_COLOR), ('--cds-on-brand', ON_COLOR),
             ('--oncolor-100', trip(ON_COLOR)), ('--oncolor-200', trip(ON_COLOR)), ('--oncolor-300', trip(ON_COLOR)),
             ('--cds-oncolor-200', alpha(ON_COLOR, 75)), ('--cds-oncolor-300', alpha(ON_COLOR, 50)),
             ('--cds-button-on-content', alpha(ON_PRIMARY, 60)), ('--cds-button-on-content-hover', alpha(ON_PRIMARY, 70)),
             ('--cds-button-on-content-ring', alpha(ON_PRIMARY, 35))]:
    add('Text', k, v)

# ---- Borders -----------------------------------------------------------------
for k, v in [('--cds-border', alpha(OV, 9)), ('--cds-border-line', alpha(OV, 14)),
             ('--cds-fizzy-lake-color-seam', alpha(OV, 12)), ('--cds-fizzy-lake-color-composer-ring', alpha(OV, 14)),
             ('--cds-fizzy-lake-color-banner-line', alpha(OV, 14)), ('--cds-fizzy-lake-color-message-line', alpha(OV, 12)),
             ('--cds-ring-color', rgb_fn(OV, 0.14)),
             ('--border-100', trip(R['fg'])), ('--border-200', trip(R['fg'])), ('--border-300', trip(R['fg'])), ('--border-400', trip(R['fg']))]:
    add('Borders / rings', k, v)

# ---- Accents -----------------------------------------------------------------
acc, acc_h, acc_t = resolve(ACCENT), hover(ACCENT), text(ACCENT)
pro, pro_h, pro_t = resolve(PRO), hover(PRO), text(PRO)
for k, v in [('--cds-fill-accent', acc), ('--cds-fill-accent-hover', acc_h),
             ('--cds-text-accent', acc_t), ('--cds-text-tint-blue', text('blue')),
             ('--cds-border-accent', alpha(acc, 22)), ('--cds-bg-accent', alpha(acc, 12)), ('--cds-bg-accent-layer', alpha(acc, 6)),
             ('--cds-fill-primary', PRIMARY), ('--cds-fill-primary-hover', PRIMARY_H), ('--cds-fill-primary-layer', alpha(ON_PRIMARY, 15)),
             ('--cds-fill-pro', pro), ('--cds-fill-pro-hover', pro_h), ('--cds-text-pro', pro_t),
             ('--cds-border-pro', alpha(pro, 22)), ('--cds-bg-pro', alpha(pro, 12)),
             ('--cds-clay', BRAND_C), ('--cds-clay-emphasized', BRAND_H),
             ('--accent-brand', trip(BRAND_C)), ('--brand-000', trip(BRAND_H)), ('--brand-100', trip(BRAND_H)), ('--brand-200', trip(BRAND_C)),
             ('--accent-000', trip(acc_t)), ('--accent-100', trip(acc)), ('--accent-200', trip(acc)), ('--accent-900', trip(mix(BG, acc, .15))),
             ('--accent-pro-000', trip(pro_t)), ('--accent-pro-100', trip(pro)), ('--accent-pro-200', trip(mix(pro, LIGHTEST, .3))),
             ('--accent-pro-900', trip(mix(BG, pro, .15)))]:
    add('Accents / brand / links', k, v)

# ---- Status ------------------------------------------------------------------
red, grn, yel = resolve(DANGER), resolve(SUCCESS), resolve(WARNING)
for k, v in [('--cds-fill-danger', red), ('--cds-fill-danger-hover', hover(DANGER)), ('--cds-text-danger', text(DANGER)), ('--cds-text-tint-red', text('red')),
             ('--cds-border-danger', alpha(red, 22)), ('--cds-bg-danger', alpha(red, 12)), ('--cds-bg-danger-layer', alpha(red, 6)),
             ('--cds-fill-success', grn), ('--cds-fill-success-hover', hover(SUCCESS)), ('--cds-text-success', text(SUCCESS)), ('--cds-text-tint-green', text('green')),
             ('--cds-border-success', alpha(grn, 25)), ('--cds-bg-success', alpha(grn, 14)),
             ('--cds-fill-warning', yel), ('--cds-fill-warning-hover', hover(WARNING)), ('--cds-text-warning', text(WARNING)), ('--cds-text-tint-yellow', text('yellow')),
             ('--cds-border-warning', alpha(yel, 29)), ('--cds-bg-warning', alpha(yel, 16)),
             ('--cds-text-tint-orange', text('orange')), ('--cds-text-tint-aqua', text('aqua')), ('--cds-text-tint-violet', text('violet')), ('--cds-text-tint-magenta', text('magenta')),
             ('--danger-000', trip(mix(text(DANGER), INK, .1))), ('--danger-100', trip(red)), ('--danger-200', trip(red)), ('--danger-900', trip(mix(BG, red, .12))),
             ('--success-000', trip(text(SUCCESS))), ('--success-100', trip(grn)), ('--success-200', trip(grn)), ('--success-900', trip(mix(BG, grn, .18))),
             ('--warning-000', trip(mix(text(WARNING), INK, .15))), ('--warning-100', trip(yel)), ('--warning-200', trip(yel)), ('--warning-900', trip(mix(BG, yel, .18)))]:
    add('Status (danger / success / warning)', k, v)

# ---- Tints -------------------------------------------------------------------
tints = {'red': 12, 'orange': 14, 'yellow': 16, 'green': 14, 'aqua': 14, 'blue': 12, 'violet': 12, 'magenta': 12}
for n, p in tints.items():
    c = HUES[n]
    add('Tint fills (--cds-fill-tint-* / --cds-bg-tint-*)', f'--cds-fill-tint-{n}', c)
    add('Tint fills (--cds-fill-tint-* / --cds-bg-tint-*)', f'--cds-bg-tint-{n}', alpha(c, p))
    add('Tint fills (--cds-fill-tint-* / --cds-bg-tint-*)', f'--cds-bg-tint-{n}-opaque', f'color-mix(in srgb, {c} {p}%, var(--cds-surface-1))')

# ---- Git / editor / misc -----------------------------------------------------
hv = lambda n: hover(n); tx = lambda n: text(n)
for k, v in [('--cds-fill-git-added', hv('green')), ('--cds-fill-git-added-hover', HUES['green']), ('--cds-fill-git-removed-hover', hv('red')),
             ('--cds-fill-git-modified', hv('yellow')), ('--cds-fill-git-modified-hover', HUES['yellow']),
             ('--cds-fill-git-merged', hv('violet')), ('--cds-fill-git-merged-hover', HUES['violet']),
             ('--cds-fill-git-closed', hv('red')), ('--cds-fill-git-closed-hover', HUES['red']),
             ('--cds-fill-git-conflicting', hv('orange')), ('--cds-fill-git-conflicting-hover', HUES['orange']),
             ('--cds-text-git-added', tx('green')), ('--cds-text-git-removed', hv('red')), ('--cds-text-git-modified', tx('yellow')),
             ('--cds-text-git-merged', tx('violet')), ('--cds-text-git-closed', HUES['red']), ('--cds-text-git-conflicting', hv('orange')),
             ('--cds-text-git-draft', R['fg_secondary']),
             ('--cds-shadow-popover', f'0 8px 24px {alpha(SHADOW, 14 * SH)}, 0 2px 6px {alpha(SHADOW, 9 * SH)}'),
             ('--df-shadow-float', f'0 0 0 .5px {alpha(SHADOW, 6 * SH)}, 0 2px 8px {alpha(SHADOW, 5 * SH)}, 0 12px 32px {alpha(SHADOW, 4 * SH)}'),
             ('--df-shadow-pop', f'0 0 0 .5px {alpha(SHADOW, 8 * SH)}, 0 4px 12px {alpha(SHADOW, 8 * SH)}, 0 16px 40px {alpha(SHADOW, 10 * SH)}')]:
    add('Git status, editor and misc', k, v)

# ---- code typography (optional) ------------------------------------------------
# code_font_size = "13.5px" (bare numbers mean px); code_line_height defaults to 1.5, unitless so it scales.
def px(v): return f'{v}px' if isinstance(v, (int, float)) else str(v)
CODE_SIZE = px(P['code_font_size']) if 'code_font_size' in P else None
if CODE_SIZE:
    for k in ('--cds-font-size-code', '--msg-code-font-size', '--prompt-text-code'):
        add('Code typography', k, CODE_SIZE)
    add('Code typography', '--cds-leading-code', str(P.get('code_line_height', 1.5)))

# ---- explicit overrides --------------------------------------------------------
TRIP_RE = re.compile(r'^[\d.]+ [\d.]+% [\d.]+%$')
pending = dict(OVERRIDE); used = 0
for g, items in groups.items():
    for i, (k, v) in enumerate(items):
        if k in pending:
            nv = pending.pop(k)
            if TRIP_RE.match(v) and nv.startswith('#'): nv = trip(nv)
            items[i] = (k, nv); used += 1
for k, v in pending.items(): add('Overrides (new variables)', k, v)

# ---- emit --------------------------------------------------------------------
seen = {}
lines = [f'/* {NAME} for Claude Desktop (generated by generator/generate.py from palette.toml; edit that, not this file).',
         f'   Unconditional {MODE} override: !important on :root and every descendant/pseudo-element so it beats',
         '   per-element redeclarations (.cds-root, .dframe-sidebar, ...) and the app\'s own light/dark rules alike. */',
         ':root, :root *, :root ::before, :root ::after {']
counts = {}
for g, items in groups.items():
    lines.append(f'  /* {g} */')
    n = 0
    for k, v in items:
        if k in seen: continue
        seen[k] = v; n += 1
        lines.append(f'  {k}: {v} !important;')
    counts[g] = n
lines.append('}')
if CODE_SIZE:  # fallback for code blocks that hardcode a size instead of using the variables
    lines.append(f'pre, pre code, .code-block__code {{ font-size: {CODE_SIZE} !important; }}')
lines.append('')
css = '\n'.join(lines)
(pal_path.parent / 'theme.css').write_text(css)

js = f"""// {NAME} for Claude Desktop. Paste into DevTools > Sources > Snippets and run (Ctrl+Enter, or Cmd+Enter on macOS).
// Generated from theme.css by generator/generate.py; do not edit by hand. Undo: document.getElementById('custom-theme').remove()
(() => {{
  const css = {json.dumps(css)};
  let el = document.getElementById('custom-theme');
  if (!el) {{ el = document.createElement('style'); el.id = 'custom-theme'; }}
  el.textContent = css;
  document.head.appendChild(el); // (re)append so it is always last in <head>
  console.log('[custom-theme] ' + {json.dumps(NAME)} + ' applied (' + css.length + ' chars)');
}})();
"""
(pal_path.parent / 'apply-theme.js').write_text(js)
for g, n in counts.items(): print(n, g)
print(sum(counts.values()), 'total', f'({used} overrides applied)')
