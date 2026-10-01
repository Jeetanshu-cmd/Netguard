// Line-art shield mark, replacing the 🛡️ emoji. Uses currentColor so it
// inherits --color-text / --color-accent from CSS and adapts to light/dark
// automatically without needing separate theme-specific assets.
export function ShieldLogo({ size = 22, className }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label="NetGuard AI logo"
    >
      <path
        d="M12 2.5l7.5 3v5.75c0 4.9-3.2 8.9-7.5 10.25-4.3-1.35-7.5-5.35-7.5-10.25V5.5l7.5-3z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path d="M12 2.5v18.98" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}
