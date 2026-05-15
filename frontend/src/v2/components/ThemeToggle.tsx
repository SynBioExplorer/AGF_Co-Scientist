import * as React from 'react';
import { motion } from 'motion/react';
import { useTheme } from '../hooks/useTheme';
import { springSoft } from '../lib/motion';
import { cn } from '../lib/cn';

export function ThemeToggle(): React.ReactElement {
  const { mode, setMode, effective } = useTheme();
  const isDark = effective === 'dark';

  function cycle(): void {
    const next = mode === 'system' ? (isDark ? 'light' : 'dark') : mode === 'dark' ? 'light' : 'dark';
    setMode(next);
  }

  return (
    <motion.button
      type="button"
      onClick={cycle}
      whileHover={{ scale: 1.06 }}
      whileTap={{ scale: 0.94 }}
      transition={springSoft}
      aria-label={`Theme: ${mode}`}
      title={`Theme: ${mode}`}
      className={cn(
        'inline-flex h-9 w-9 items-center justify-center rounded-full border border-neutral-200 bg-white text-neutral-700',
        'dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300',
      )}
    >
      <motion.span
        key={isDark ? 'dark' : 'light'}
        initial={{ rotate: -90, opacity: 0 }}
        animate={{ rotate: 0, opacity: 1 }}
        transition={springSoft}
        aria-hidden
      >
        {isDark ? '☾' : '☀'}
      </motion.span>
    </motion.button>
  );
}
