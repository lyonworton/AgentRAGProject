import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.97] select-none",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm hover:shadow-md",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-sm",
        outline: "border border-border bg-card hover:bg-accent hover:text-accent-foreground hover:border-primary/40 transition-colors duration-150",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors duration-150",
        ghost: "hover:bg-accent hover:text-accent-foreground transition-colors duration-150",
        link: "text-primary underline-offset-4 hover:underline",
        glow: "bg-primary text-primary-foreground shadow-card hover:shadow-card-hover hover:ring-2 hover:ring-primary/20 transition-shadow duration-200",
        subtle: "bg-accent/60 text-accent-foreground hover:bg-accent/80 border border-border/50 transition-colors duration-150",
        success: "bg-success text-success-foreground hover:bg-success/90 shadow-sm",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-7.5 rounded-md px-2.5 text-xs",
        lg: "h-11 rounded-lg px-8 text-base",
        icon: "h-9 w-9 rounded-lg",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props}
    />
  )
)
Button.displayName = "Button"

export { Button, buttonVariants }
