import type { Transition, Variants } from 'motion/react';

export const springSoft: Transition = {
  type: 'spring',
  stiffness: 400,
  damping: 30,
};

export const springSnappy: Transition = {
  type: 'spring',
  stiffness: 550,
  damping: 32,
};

export const tweenFast: Transition = {
  type: 'tween',
  duration: 0.2,
  ease: [0.32, 0.72, 0, 1],
};

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: tweenFast },
  exit: { opacity: 0, y: -8, transition: { ...tweenFast, duration: 0.15 } },
};

export const listContainer: Variants = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.03,
    },
  },
};

export const listItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: springSoft,
  },
};

export const buttonHoverTap = {
  whileHover: { scale: 1.02 },
  whileTap: { scale: 0.98 },
  transition: springSoft,
};

export const wizardStep: Variants = {
  initial: { opacity: 0, y: 30, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1, transition: springSoft },
  exit: { opacity: 0, y: -30, scale: 0.98, transition: { ...tweenFast } },
};
