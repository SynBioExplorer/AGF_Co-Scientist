import * as React from 'react';
import { motion } from 'motion/react';
import { cn } from '../lib/cn';
import { listItem, springSoft } from '../lib/motion';
import type { Hypothesis } from '../lib/types';

export interface HypothesisCardProps {
  hypothesis: Hypothesis;
  onClick?: () => void;
  highlighted?: boolean;
  index?: number;
}

export function HypothesisCard({
  hypothesis,
  onClick,
  highlighted,
  index,
}: HypothesisCardProps): React.ReactElement {
  return (
    <motion.article
      layoutId={`hypothesis-${hypothesis.id}`}
      variants={listItem}
      whileHover={{ y: -2 }}
      transition={springSoft}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (!onClick) return;
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        'card cursor-pointer p-5 transition-shadow hover:shadow-md',
        highlighted && 'ring-2 ring-sky-500/40',
      )}
      data-testid={`hypothesis-card-${hypothesis.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          {typeof index === 'number' ? (
            <span className="mono inline-block text-[10px] uppercase tracking-widest text-neutral-500 dark:text-neutral-400">
              #{(index + 1).toString().padStart(2, '0')}
            </span>
          ) : null}
          <h3 className="mt-1 line-clamp-2 text-base font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
            {hypothesis.title}
          </h3>
        </div>
        <span className="mono shrink-0 rounded-md bg-neutral-100 px-2 py-1 text-[11px] font-medium text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200">
          ELO {Math.round(hypothesis.elo_rating)}
        </span>
      </div>
      <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-neutral-600 dark:text-neutral-300">
        {hypothesis.summary}
      </p>
    </motion.article>
  );
}
