import * as React from "react";
import { cn } from "@/lib/utils";

/** Native form controls, styled: they are the most reliable on phones. */

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("block text-xs font-medium text-fg-muted", className)} {...props} />;
}

export function Field({ label, hint, children, className }: { label?: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("space-y-1", className)}>
      {label && <Label>{label}</Label>}
      {children}
      {hint && <p className="text-xs text-fg-muted">{hint}</p>}
    </div>
  );
}

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "h-10 w-full rounded-md border bg-bg-elev px-2.5 pr-7 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 appearance-none bg-no-repeat bg-[right_0.5rem_center] bg-[length:12px]",
      className,
    )}
    style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M2 4l4 4 4-4' fill='none' stroke='%23888' stroke-width='1.5'/%3E%3C/svg%3E\")" }}
    {...props}
  >
    {children}
  </select>
));
Select.displayName = "Select";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn("h-10 w-full rounded-md border bg-bg-elev px-2.5 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50", className)} {...props} />
));
Input.displayName = "Input";

export function Checkbox({ label, className, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label?: React.ReactNode }) {
  return (
    <label className={cn("inline-flex min-h-10 cursor-pointer items-center gap-2 text-sm", className)}>
      <input type="checkbox" className="h-4 w-4 accent-[var(--accent)]" {...props} />
      {label && <span>{label}</span>}
    </label>
  );
}

export function Switch({ checked, onCheckedChange, label, className, disabled }: { checked: boolean; onCheckedChange: (v: boolean) => void; label?: React.ReactNode; className?: string; disabled?: boolean }) {
  return (
    <label className={cn("inline-flex min-h-10 cursor-pointer items-center gap-2 text-sm", disabled && "opacity-50", className)}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn("relative h-6 w-10 rounded-full border transition-colors", checked ? "bg-accent border-accent" : "bg-bg-muted")}
      >
        <span className={cn("absolute top-0.5 h-4.5 w-4.5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[18px]" : "translate-x-0.5")} style={{ height: 18, width: 18 }} />
      </button>
      {label && <span>{label}</span>}
    </label>
  );
}

export function Slider({ className, valueLabel, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { valueLabel?: React.ReactNode }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <input type="range" className="h-2 w-full accent-[var(--accent)]" {...props} />
      {valueLabel !== undefined && <span className="w-12 shrink-0 text-right text-sm tabular-nums">{valueLabel}</span>}
    </div>
  );
}

export function NumberStepper({ value, onChange, min, max, step = 1, className, ariaLabel }: { value: number; onChange: (v: number) => void; min: number; max: number; step?: number; className?: string; ariaLabel?: string }) {
  const clampV = (v: number) => Math.min(max, Math.max(min, v));
  return (
    <div className={cn("inline-flex h-10 items-stretch rounded-md border bg-bg-elev", className)}>
      <button type="button" aria-label="decrease" className="w-9 text-lg hover:bg-bg-muted" onClick={() => onChange(clampV(value - step))}>
        −
      </button>
      <input
        aria-label={ariaLabel}
        type="number"
        inputMode="numeric"
        className="w-14 border-x bg-transparent text-center text-sm tabular-nums outline-none"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => {
          const v = Number(e.target.value);
          if (Number.isFinite(v)) onChange(clampV(v));
        }}
      />
      <button type="button" aria-label="increase" className="w-9 text-lg hover:bg-bg-muted" onClick={() => onChange(clampV(value + step))}>
        +
      </button>
    </div>
  );
}
