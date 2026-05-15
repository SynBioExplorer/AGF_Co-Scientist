import * as React from 'react';
import { motion } from 'motion/react';
import { wizardStep } from '../lib/motion';

export interface WizardCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function WizardCard({
  title,
  subtitle,
  children,
  footer,
}: WizardCardProps): React.ReactElement {
  return (
    <motion.section
      variants={wizardStep}
      initial="initial"
      animate="animate"
      exit="exit"
      className="card relative z-10 mx-auto w-full max-w-2xl px-8 py-10 shadow-xl"
      data-testid="wizard-card"
    >
      <header className="mb-6">
        <h1 className="text-3xl font-bold tracking-tightest text-neutral-900 dark:text-neutral-50">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-2 text-base text-neutral-600 dark:text-neutral-400">{subtitle}</p>
        ) : null}
      </header>
      <div className="space-y-4">{children}</div>
      {footer ? <footer className="mt-8 flex items-center justify-between">{footer}</footer> : null}
    </motion.section>
  );
}
