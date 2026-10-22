#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["tinycss2"]
# ///
"""Extract CSS custom properties (--variables) from a stylesheet dump.

Usage (from css-dump/): uv run extract_vars.py all.css [-o vars.css] [--colors-only]

Keeps each selector and its @media/@supports/@layer wrappers so light/dark
variants stay intact, drops every non-variable declaration (and Tailwind's
internal --tw-* variables), and removes duplicate rules.
"""
import argparse
import re
from pathlib import Path

import tinycss2

# At-rules whose blocks hold rules we want to descend into.
CONTAINER_AT_RULES = {"media", "supports", "layer", "container", "document", "scope"}

COLOR_VALUE = re.compile(
    r"#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix|light-dark)\("
    # Bare HSL/RGB channel triplets, e.g. "0 0% 100%" (Tailwind/shadcn style)
    r"|^\s*\d+(?:\.\d+)?(?:deg)?\s+\d+(?:\.\d+)?%\s+\d+(?:\.\d+)?%(?:\s*/\s*[\d.]+%?)?\s*$",
    re.I,
)


def extract(rules, colors_only: bool, wrappers: tuple[str, ...] = ()):
    for rule in rules:
        if rule.type == "qualified-rule":
            selector = tinycss2.serialize(rule.prelude).strip()
            decls = []
            for d in tinycss2.parse_blocks_contents(rule.content, skip_whitespace=True, skip_comments=True):
                # --tw-* are Tailwind's per-utility internals, not theme tokens
                if d.type == "declaration" and d.name.startswith("--") and not d.name.startswith("--tw-"):
                    value = tinycss2.serialize(d.value).strip()
                    if not colors_only or COLOR_VALUE.search(value):
                        decls.append(f"{d.name}: {value}{' !important' if d.important else ''};")
                elif d.type == "qualified-rule":  # native CSS nesting
                    yield from extract([d], colors_only, wrappers + (f"{selector} {{",))
            if decls:
                yield wrappers, selector, tuple(decls)
        elif rule.type == "at-rule" and rule.lower_at_keyword in CONTAINER_AT_RULES and rule.content:
            header = f"@{rule.at_keyword} {tinycss2.serialize(rule.prelude).strip()} {{"
            inner = tinycss2.parse_rule_list(rule.content, skip_whitespace=True, skip_comments=True)
            yield from extract(inner, colors_only, wrappers + (header,))


def render(entries) -> str:
    out = []
    for wrappers, selector, decls in entries:
        depth = len(wrappers)
        lines = [f"{'  ' * i}{w}" for i, w in enumerate(wrappers)]
        pad = "  " * depth
        lines.append(f"{pad}{selector} {{")
        lines += [f"{pad}  {d}" for d in decls]
        lines.append(f"{pad}}}")
        lines += [f"{'  ' * i}}}" for i in reversed(range(depth))]
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("vars.css"))
    parser.add_argument("--colors-only", action="store_true", help="keep only variables whose value looks like a color")
    args = parser.parse_args()

    sheet = tinycss2.parse_stylesheet(
        args.file.read_text(encoding="utf-8", errors="replace"), skip_whitespace=True, skip_comments=True
    )
    entries = list(dict.fromkeys(extract(sheet, args.colors_only)))  # dedupe, keep order
    args.output.write_text(render(entries))

    names = {d.split(":", 1)[0] for _, _, decls in entries for d in decls}
    print(f"{len(entries):,} rules, {len(names):,} unique variables -> {args.output}")


if __name__ == "__main__":
    main()
