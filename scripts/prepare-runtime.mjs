/** Serve the pinned, unmodified Pyodide runtime from our own deployment. */
import { copyFile, mkdir } from 'node:fs/promises';
const files = [
  'pyodide.mjs',
  'pyodide.asm.mjs',
  'pyodide.asm.wasm',
  'pyodide-lock.json',
  'python_stdlib.zip',
];
const destination = new URL('../public/runtime/', import.meta.url);
await mkdir(destination, { recursive: true });
for (const file of files) {
  await copyFile(
    new URL(`../node_modules/pyodide/${file}`, import.meta.url),
    new URL(file, destination),
  );
}
console.log('Prepared pinned Pyodide runtime: five unmodified local assets.');
