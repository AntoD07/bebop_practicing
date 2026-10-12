import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-colors select-none disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:translate-y-px",
  {
    variants: {
      variant: {
        default: "bg-accent text-accent-fg hover:opacity-90",
        outline: "border bg-bg-elev hover:bg-bg-muted",
        ghost: "hover:bg-bg-muted",
        soft: "bg-accent-soft text-accent hover:opacity-90",
        danger: "bg-danger text-white hover:opacity-90",
      },
      size: {
        sm: "h-8 px-2.5 text-sm",
        md: "h-10 px-3.5 text-sm",
        lg: "h-12 px-5 text-base",
        icon: "h-10 w-10",
        iconLg: "h-14 w-14 text-xl",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>;

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, type = "button", ...props }, ref) => (
  <button ref={ref} type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
));
Button.displayName = "Button";
