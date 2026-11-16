/**
 * The only scripts a box page may run inside Caixa: the generated pages' own lightbox
 * (`tools/chattr/src/chattr/templates/lightbox.js`), allowed by the SHA-256 of its exact text. Any
 * other script in a page, whatever put it there, is refused by the browser.
 *
 * When lightbox.js changes, its hash changes: Chattr's tests compute it from a rendered page and fail
 * until the new value is written here.
 */
export const PAGE_SCRIPTS: readonly string[] = ['sha256-USdE6WO3aXb2/ZFcN/hasOy2FqqhtEhakS5FFGDQOMs=']
