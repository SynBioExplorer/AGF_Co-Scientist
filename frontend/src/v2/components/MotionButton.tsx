import * as React from 'react';
import { motion, type HTMLMotionProps } from 'motion/react';
import { cn } from '../lib/cn';
import { springSoft } from '../lib/motion';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

export interface MotionButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
  children?: React.ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-sky-500 text-white hover:bg-sky-600 dark:bg-sky-400 dark:text-neutral-950 dark:hover:bg-sky-300 shadow-sm',
  secondary:
    'bg-neutral-100 text-neutral-900 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700',
  ghost:
    'bg-transparent text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800',
  danger:
    'bg-red-500 text-white hover:bg-red-600 dark:bg-red-400 dark:text-neutral-950 dark:hover:bg-red-300',
};

const sizeClasses: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

export const MotionButton = React.forwardRef<HTMLButtonElement, MotionButtonProps>(
  (
    { variant = 'primary', size = 'md', isLoading, className, children, disabled, ...rest },
    ref,
  ) => {
    const isDisabled = disabled || isLoading;
    return (
      <motion.button
        ref={ref}
        whileHover={isDisabled ? undefined : { scale: 1.02 }}
        whileTap={isDisabled ? undefined : { scale: 0.98 }}
        transition={springSoft}
        disabled={isDisabled}
        className={cn(
          'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-neutral-950',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        {...rest}
      >
        {isLoading ? (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : null}
        {children}
      </motion.button>
    );
  },
);
MotionButton.displayName = 'MotionButton';
