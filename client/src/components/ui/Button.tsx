import { cva, type VariantProps } from "class-variance-authority";
import {
  type ButtonHTMLAttributes,
  type ReactElement,
  type Ref,
  cloneElement,
  isValidElement,
} from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[#FFC300] text-[#1C1C1C] hover:bg-[#FFD54F] font-semibold",
        outline:
          "border border-[hsl(var(--border))] bg-transparent text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))]",
        ghost: "hover:bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]",
        destructive: "bg-red-600 text-white hover:bg-red-700",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-12 px-6 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
    ref?: Ref<HTMLButtonElement>;
  };

/**
 * Primary action button with variant (`default`, `outline`, `ghost`, `destructive`)
 * and size (`default`, `sm`, `lg`, `icon`) support. Use `asChild` to render as a child element.
 */
export function Button({
  className,
  variant,
  size,
  asChild = false,
  children,
  ref,
  ...props
}: ButtonProps) {
  const classes = cn(buttonVariants({ variant, size, className }));

  if (asChild && isValidElement(children)) {
    const child = children as ReactElement<{
      className?: string;
      ref?: Ref<HTMLElement>;
    }>;
    return cloneElement(child, {
      className: cn(classes, child.props.className),
      ref,
    });
  }

  return (
    <button ref={ref} className={classes} {...props}>
      {children}
    </button>
  );
}
