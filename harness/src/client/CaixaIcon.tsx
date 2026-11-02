/** The sidebar glyph: a box with a lid. Decorative; the sidebar supplies the accessible label. */
export function CaixaIcon({ size }: { readonly size?: number }) {
  const edge = size ?? 20
  return (
    <svg width={edge} height={edge} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
      <path d="M3 8.5h18v3H3z" />
      <path d="M4.5 11.5V20h15v-8.5" />
      <path d="M10 15h4" />
    </svg>
  )
}
