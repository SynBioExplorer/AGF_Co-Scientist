import React from 'react';
import {
  BarChart,
  Bar,
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

export const QualityDistribution: React.FC<Props> = ({ hypotheses }) => {
  // Group hypotheses into Elo rating ranges
  const ranges = [
    { label: '< 1100', min: 0, max: 1100 },
    { label: '1100-1200', min: 1100, max: 1200 },
    { label: '1200-1300', min: 1200, max: 1300 },
    { label: '1300-1400', min: 1300, max: 1400 },
    { label: '> 1400', min: 1400, max: Infinity },
  ];

  const data = ranges.map((range) => ({
    range: range.label,
    count: hypotheses.filter(
      (h) => h.elo_rating >= range.min && h.elo_rating < range.max
    ).length,
  }));

  return (
    <Card>
      <h3 className="text-lg font-semibold mb-4">Hypothesis Quality Distribution</h3>
      {hypotheses.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No hypothesis data available yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="range" />
            <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="count" fill="#6366f1" name="Hypotheses" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
};
