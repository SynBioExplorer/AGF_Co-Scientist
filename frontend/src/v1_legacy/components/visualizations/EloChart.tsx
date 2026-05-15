import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { Hypothesis } from '../../types';
import { Card } from '../common/Card';

interface Props {
  hypotheses: Hypothesis[];
}

export const EloChart: React.FC<Props> = ({ hypotheses }) => {
  const sortedHypotheses = [...hypotheses]
    .sort((a, b) => b.elo_rating - a.elo_rating)
    .slice(0, 10);

  const data = sortedHypotheses.map((h, index) => ({
    rank: index + 1,
    name: h.title.substring(0, 25) + (h.title.length > 25 ? '...' : ''),
    elo: Math.round(h.elo_rating),
  }));

  return (
    <Card>
      <h3 className="text-lg font-semibold mb-4">Top 10 Hypotheses by Elo Rating</h3>
      {data.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No hypothesis data available yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="rank"
              label={{ value: 'Rank', position: 'bottom', offset: -5 }}
            />
            <YAxis
              domain={['dataMin - 50', 'dataMax + 50']}
              label={{ value: 'Elo Rating', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip
              formatter={(value) => [value || 0, 'Elo']}
              labelFormatter={(rank) => `Rank #${rank}`}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="elo"
              stroke="#6366f1"
              strokeWidth={2}
              dot={{ fill: '#6366f1', strokeWidth: 2 }}
              name="Elo Rating"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
};
