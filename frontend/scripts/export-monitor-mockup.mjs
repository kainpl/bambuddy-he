import { build } from 'vite';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const built = resolve(frontend, '../temp/monitor-mockup');
const destination = resolve(frontend, '../temp/monitor-delivery/BamDude-monitor-mockup.html');
await build({ root: frontend, configFile: resolve(frontend, 'vite.monitor.config.ts') });

const mime = { '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.woff2': 'font/woff2' };
async function dataUrl(asset) {
  const bytes = await readFile(resolve(frontend, 'public', asset.replace(/^\//, '')));
  const type = mime[extname(asset)];
  if (!type) throw new Error(`Unsupported embedded asset: ${asset}`);
  return `data:${type};base64,${bytes.toString('base64')}`;
}

let html = await readFile(resolve(built, 'monitor-mockup.html'), 'utf8');
const scripts = [...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g)];
const styles = [...html.matchAll(/<link\b[^>]*\brel="stylesheet"[^>]*\bhref="([^"]+)"[^>]*>/g)];
if (scripts.length !== 1 || styles.length !== 1) throw new Error('Expected one JS bundle and one CSS bundle. Recheck export handling before sharing.');

const assets = {};
for (const path of [
  '/img/brand/mark-on-dark-64.png',
  ...['p1s', 'x1c', 'a1', 'h2d', 'p2s', 'a1mini'].map(model => `/img/printers/${model}.png`),
]) assets[path] = await dataUrl(path);

let css = await readFile(resolve(built, styles[0][1].replace(/^\//, '')), 'utf8');
for (const match of [...css.matchAll(/url\((['"]?)([^)'"\s]+)\1\)/g)]) {
  if (match[2].startsWith('data:') || match[2].startsWith('#')) continue;
  css = css.replaceAll(match[0], `url("${await dataUrl(match[2])}")`);
}
const js = await readFile(resolve(built, scripts[0][1].replace(/^\//, '')), 'utf8');
html = html.replace(scripts[0][0], () => `<script>window.__BAMDUDE_MONITOR_ASSETS__=${JSON.stringify(assets)};</script>\n<script type="module">${js.replace(/<\/script/gi, '<\\/script')}</script>`);
html = html.replace(styles[0][0], () => `<style>${css.replace(/<\/style/gi, '<\\/style')}</style>`);
html = html.replace('/img/brand/favicon.ico', await dataUrl('/img/brand/favicon.ico'));
if (/<(?:script|link)\b[^>]*(?:src|href)="(?!data:)/i.test(html)) throw new Error('The export still has an external script or stylesheet.');

await mkdir(dirname(destination), { recursive: true });
await writeFile(destination, html, 'utf8');
console.log(`Portable HTML: ${destination}`);
console.log(`${(Buffer.byteLength(html) / 1024 / 1024).toFixed(2)} MB; scripts, styles, fonts and printer images embedded.`);
