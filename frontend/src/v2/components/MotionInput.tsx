import * as React from 'react';
import { motion } from 'motion/react';
import { cn } from '../lib/cn';
import { springSoft } from '../lib/motion';

export interface MotionInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  hint?: string;
  error?: string;
  monoValue?: boolean;
  rightSlot?: React.ReactNode;
}

export const MotionInput = React.forwardRef<HTMLInputElement, MotionInputProps>(
  ({ label, hint, error, monoValue, rightSlot, className, id, ...rest }, ref) => {
    const reactId = React.useId();
    const inputId = id || reactId;
    return (
      <div className="flex flex-col gap-1.5">
        {label ? (
          <label htmlFor={inputId} className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
            {label}
          </label>
        ) : null}
        <motion.div
          transition={springSoft}
          className={cn(
            'flex items-center gap-2 rounded-xl border bg-white px-3 py-2 transition-colors',
            'border-neutral-200 focus-within:border-sky-500 focus-within:ring-2 focus-within:ring-sky-500/30',
            'dark:bg-neutral-900 dark:border-neutral-700 dark:focus-within:border-sky-400',
            error ? 'border-red-500 focus-within:border-red-500 focus-within:ring-red-500/30' : '',
          )}
        >
          <input
            id={inputId}
            ref={ref}
            className={cn(
              'flex-1 bg-transparent text-sm text-neutral-900 placeholder:text-neutral-400 outline-none dark:text-neutral-100 dark:placeholder:text-neutral-500',
              monoValue && 'font-mono',
              className,
            )}
            {...rest}
          />
          {rightSlot}
        </motion.div>
        {error ? (
          <span className="text-xs text-red-500">{error}</span>
        ) : hint ? (
          <span className="text-xs text-neutral-500 dark:text-neutral-400">{hint}</span>
        ) : null}
      </div>
    );
  },
);
MotionInput.displayName = 'MotionInput';
