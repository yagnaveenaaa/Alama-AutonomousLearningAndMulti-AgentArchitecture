import styles from "./ui.module.css";

export function PageShell({
  kicker,
  title,
  lede,
  children,
  className,
}: {
  kicker?: string;
  title: string;
  lede?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`${styles.shell} ${className ?? ""}`}>
      {kicker ? <p className={`${styles.kicker} rise`}>{kicker}</p> : null}
      <h1 className={`${styles.title} rise`}>{title}</h1>
      {lede ? <p className={`${styles.lede} rise-delay`}>{lede}</p> : null}
      {children}
    </div>
  );
}

export { styles as ui };
