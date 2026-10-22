// Dump every stylesheet of the current page into all.css (downloaded by the browser).
// Run in the Claude Desktop DevTools Console, or save it as a Sources > Snippets entry.
const parts = [];
for (const s of [...document.styleSheets, ...document.adoptedStyleSheets]) {
  const label = `/* ${s.href || 'inline <style>'} */\n`;
  try {
    parts.push(label + [...s.cssRules].map(r => r.cssText).join('\n'));
  } catch {
    // Cross-origin sheets block cssRules, so fetch the file directly
    if (s.href) parts.push(label + await (await fetch(s.href)).text());
  }
}
const css = parts.join('\n\n');
Object.assign(document.createElement('a'), {
  href: URL.createObjectURL(new Blob([css], { type: 'text/css' })),
  download: 'all.css',
}).click();
console.log(`${parts.length} stylesheets, ${(css.length / 1024).toFixed(0)} KB`);
