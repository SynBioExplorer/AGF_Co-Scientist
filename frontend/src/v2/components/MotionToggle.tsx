import * as React from 'react';
import * as Switch from '@radix-ui/react-switch';
import { motion } from 'motion/react';
import { cn } from '../lib/cn';
import { springSoft } from '../lib/motion';

export interface MotionToggleProps {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  label?: string;
  description?: string;
  id?: string;
  disabled?: boolean;
}

export function MotionToggle({
  checked,
  onCheckedChange,
  label,
  description,
  id,
  disabled,
}: MotionToggleProps): React.ReactElement {
  const reactId = React.useId();
  const switchId = id || reactId;
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="flex-1">
        {label ? (
          <label htmlFor={switchId} className="text-sm font-medium text-neutral-800 dark:text-neutral-200">
            {label}
          </label>
        ) : null}
        {description ? (
          <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">{description}</p>
        ) : null}
      </div>
      <Switch.Root
        id={switchId}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className={cn(
          'relative h-6 w-11 cursor-pointer rounded-full transition-colors',
          'bg-neutral-300 data-[state=checked]:bg-sky-500 dark:bg-neutral-700 dark:data-[state=checked]:bg-sky-400',
          'disabled:opacity-50',
        )}
      >
        <Switch.Thumb asChild>
          <motion.span
            layout
            transition={springSoft}
            className="block h-5 w-5 translate-x-0.5 rounded-full bg-white shadow data-[state=checked]:translate-x-[22px]"
            data-state={checked ? 'checked' : 'unchecked'}
          />
        </Switch.Thumb>
      </Switch.Root>
    </div>
  );
}
