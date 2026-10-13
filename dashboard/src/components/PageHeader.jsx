import styles from './PageHeader.module.css'

// Shared header for dashboard pages: mono eyebrow, display heading, one-line
// description, and a slot on the right for status / controls.
export function PageHeader({ id, eyebrow, title, description, children }) {
  return (
    <header className={styles.header}>
      <div className={styles.text}>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1 id={id} className={styles.title}>{title}</h1>
        {description && <p className={styles.description}>{description}</p>}
      </div>
      {children && <div className={styles.side}>{children}</div>}
    </header>
  )
}
