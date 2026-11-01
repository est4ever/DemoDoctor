import { clsx } from "clsx";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  PropsWithChildren,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

export function Panel({
  children,
  className,
  bodyClassName,
  title,
  action,
}: PropsWithChildren<{
  className?: string;
  bodyClassName?: string;
  title?: string;
  action?: ReactNode;
}>) {
  return (
    <section
      className={clsx(
        "rounded-2xl border border-[var(--border)] bg-[var(--panel)] shadow-[var(--shadow)]",
        className,
      )}
    >
      {title ? (
        <header className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-3.5 md:px-6">
          <h2 className="text-[0.95rem] font-semibold tracking-wide text-[var(--muted)]">
            {title}
          </h2>
          {action}
        </header>
      ) : null}
      <div className={clsx("p-5 md:p-6", bodyClassName)}>{children}</div>
    </section>
  );
}

export function Button({
  className,
  variant = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "ghost";
}) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-[0.95rem] font-medium transition disabled:opacity-40",
        variant === "primary" &&
          "bg-[var(--accent)] text-white hover:brightness-110",
        variant === "default" &&
          "border border-[var(--border)] bg-[var(--panel-soft)] text-[var(--text)] hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]",
        variant === "ghost" &&
          "bg-transparent text-[var(--muted)] hover:bg-[var(--panel-soft)] hover:text-[var(--text)]",
        className,
      )}
      {...props}
    />
  );
}

export function Slider({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="range"
      className={clsx(
        "h-2 w-full cursor-pointer accent-[var(--accent)]",
        className,
      )}
      {...props}
    />
  );
}

export function Select({
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={clsx(
        "rounded-xl border border-[var(--border)] bg-white px-3.5 py-2.5 text-[0.95rem] outline-none focus:border-[var(--accent)]",
        className,
      )}
      {...props}
    />
  );
}

export function Badge({
  children,
  tone = "muted",
}: PropsWithChildren<{
  tone?:
    | "muted"
    | "warn"
    | "ok"
    | "accent"
    | "danger"
    | "inferred"
    | "observed";
}>) {
  const map: Record<string, string> = {
    muted: "bg-[var(--panel-soft)] text-[var(--muted)] border-[var(--border)]",
    warn: "bg-[var(--warn-soft)] text-[var(--warn)] border-[var(--warn)]/25",
    ok: "bg-[var(--ok-soft)] text-[var(--ok)] border-[var(--ok)]/25",
    accent:
      "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent)]/25",
    danger: "bg-[#382525] text-[var(--danger)] border-[var(--danger)]/25",
    inferred:
      "bg-[var(--warn-soft)] text-[var(--inferred)] border-[var(--warn)]/30",
    observed:
      "bg-[var(--ok-soft)] text-[var(--observed)] border-[var(--ok)]/30",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[0.8rem] font-medium",
        map[tone],
      )}
    >
      {children}
    </span>
  );
}

export function EvidenceChip({
  id,
  active,
  onClick,
}: {
  id: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      className={clsx(
        "rounded-md border px-2 py-0.5 font-mono text-[0.8rem] transition",
        active
          ? "border-[var(--accent)] bg-[var(--accent)] text-white"
          : "border-[var(--accent)]/30 bg-[var(--accent-soft)] text-[var(--accent)] hover:border-[var(--accent)]",
      )}
    >
      {id}
    </button>
  );
}
