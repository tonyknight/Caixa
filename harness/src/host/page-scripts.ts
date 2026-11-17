/**
 * The only scripts a box page may run inside Caixa, each allowed by the SHA-256 of its exact text:
 * the pages' lightbox (`tools/chattr/src/chattr/templates/lightbox.js`) and the index's categories
 * (`index.js`, which may also call Caixa to save a person's category). Any other script in a page,
 * whatever put it there, is refused by the browser.
 *
 * When either file changes, its hash changes: Chattr's tests compute it from a rendered page and fail
 * until the new value is written here.
 */
export const PAGE_SCRIPTS: readonly string[] = [
  'sha256-USdE6WO3aXb2/ZFcN/hasOy2FqqhtEhakS5FFGDQOMs=', // lightbox.js
  'sha256-kuCExLzFJvkNnkkp9YXxKYIpCCVFJH+njgEjZYlA0SE=', // index.js
]
