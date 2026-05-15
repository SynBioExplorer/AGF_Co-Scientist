import React, { useState } from 'react';
import type { Hypothesis } from '../../types';
import { HypothesisCard } from './HypothesisCard';
import { Loading } from '../common/Loading';

interface HypothesesListProps {
  hypotheses: Hypothesis[];
  loading: boolean;
  onSelectHypothesis: (id: string) => void;
}

export const HypothesisList: React.FC<HypothesesListProps> = ({
  hypotheses,
  loading,
  onSelectHypothesis,
}) => {
  const [sortBy, setSortBy] = useState<'elo' | 'date'>('elo');

  const sortedHypotheses = [...hypotheses].sort((a, b) => {
    if (sortBy === 'elo') {
      return b.elo_rating - a.elo_rating;
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  if (loading) {
    return <Loading message="Loading hypotheses..." />;
  }

  return (
    <div>
      <div className="mb-4 flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-800">
          Hypotheses ({hypotheses.length})
        </h2>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'elo' | 'date')}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="elo">Sort by Elo Rating</option>
          <option value="date">Sort by Date</option>
        </select>
      </div>

      {sortedHypotheses.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No hypotheses generated yet. Start by asking a research question in the chat.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sortedHypotheses.map((hypothesis) => (
            <HypothesisCard
              key={hypothesis.id}
              hypothesis={hypothesis}
              onClick={() => onSelectHypothesis(hypothesis.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
};
