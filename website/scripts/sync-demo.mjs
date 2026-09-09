import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
const source = new URL('../../src/autodev/web/', import.meta.url);
const target = new URL('../public/demo/', import.meta.url);
await mkdir(target, { recursive: true });
for (const name of ['app.js', 'demo.js', 'style.css'])
  await copyFile(new URL(name, source), new URL(name, target));
const html = (await readFile(new URL('index.html', source), 'utf8'))
  .replaceAll('__PROJECT_TITLE__', 'Autodev fleet demo')
  .replace('__BOOTSTRAP__', JSON.stringify({ demoOnly: true, token: '' }))
  .replaceAll('/assets/', '/demo/')
  .replace('<body>', '<body class="demo-only">')
  .replace(
    '</head>',
    '<style>.demo-only [data-nav="settings"],.demo-only #refresh{display:none}</style></head>',
  );
await writeFile(new URL('index.html', target), html);
console.log('Synced the canonical fleet UI and simulation into the website.');
