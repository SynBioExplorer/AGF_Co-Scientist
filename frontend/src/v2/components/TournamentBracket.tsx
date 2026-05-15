import * as React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '../lib/cn';
import { springSoft } from '../lib/motion';
import type { TournamentBracketData, TournamentMatch } from '../lib/types';

export interface TournamentBracketProps {
  data?: TournamentBracketData;
}

function Slot({ name, isWinner }: { name?: string; isWinner?: boolean }): React.ReactElement {
  return (
    <motion.div
      layout
      transition={springSoft}
      className={cn(
        'mono truncate rounded-md border px-3 py-1.5 text-xs',
        isWinner
          ? 'border-sky-500/40 bg-sky-500/10 text-sky-900 dark:text-sky-200'
          : 'border-neutral-200 bg-white text-neutral-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300',
      )}
    >
      {name ?? '—'}
    </motion.div>
  );
}

function MatchCard({ match }: { match: TournamentMatch }): React.ReactElement {
  return (
    <motion.div
      layout
      layoutId={`match-${match.id}`}
      transition={springSoft}
      className="card flex w-44 flex-col gap-1.5 p-2"
    >
      <Slot
        name={match.a?.title}
        isWinner={match.winner_id === match.a?.id}
      />
      <Slot
        name={match.b?.title}
        isWinner={match.winner_id === match.b?.id}
      />
    </motion.div>
  );
}

export function TournamentBracket({ data }: TournamentBracketProps): React.ReactElement {
  const rounds = data?.rounds ?? [];
  if (rounds.length === 0) {
    return (
      <div className="card flex h-32 items-center justify-center text-sm text-neutral-500">
        No matches yet — tournament will appear when ranking begins.
      </div>
    );
  }
  return (
    <div className="flex items-start gap-6 overflow-x-auto pb-2">
      <AnimatePresence initial={false}>
        {rounds.map((round, ri) => (
          <motion.div
            key={`round-${ri}`}
            layout
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={springSoft}
            className="flex flex-col gap-3"
          >
            <span className="mono text-[10px] uppercase tracking-widest text-neutral-500">
              Round {ri + 1}
            </span>
            <div className="flex flex-col gap-4">
              {round.map((m) => (
                <MatchCard key={m.id} match={m} />
              ))}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
