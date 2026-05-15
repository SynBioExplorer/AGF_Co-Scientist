import React from 'react';
import type { Hypothesis } from '../../types';
import { Card } from '../common/Card';

interface HypothesisCardProps {
  hypothesis: Hypothesis;
  onClick?: () => void;
}

export const HypothesisCard: React.FC<HypothesisCardProps> = ({ hypothesis, onClick }) => {
  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer" onClick={onClick}>
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-semibold text-gray-800 flex-1">{hypothesis.title}</h3>
        <div className="ml-4 text-right">
          <div className="text-xl font-bold text-indigo-600">
            {Math.round(hypothesis.elo_rating)}
          </div>
          <div className="text-xs text-gray-500">Elo Rating</div>
        </div>
      </div>

      <p className="text-sm text-gray-600 mb-3 line-clamp-2">{hypothesis.summary}</p>

      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span className={`px-2 py-1 rounded ${
          hypothesis.status === 'completed' ? 'bg-green-100 text-green-700' :
          hypothesis.status === 'processing' ? 'bg-blue-100 text-blue-700' :
          'bg-gray-100 text-gray-700'
        }`}>
          {hypothesis.status}
        </span>
        <span>•</span>
        <span>{new Date(hypothesis.created_at).toLocaleDateString()}</span>
      </div>
    </Card>
  );
};
