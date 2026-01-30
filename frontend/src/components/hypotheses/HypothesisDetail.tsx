import React from 'react';
import type { HypothesisDetail as HypothesisDetailType } from '../../types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';

interface HypothesisDetailProps {
  hypothesis: HypothesisDetailType;
  onClose: () => void;
}

export const HypothesisDetail: React.FC<HypothesisDetailProps> = ({ hypothesis, onClose }) => {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{hypothesis.title}</h1>
          <p className="text-gray-500 mt-1">
            Created {new Date(hypothesis.created_at).toLocaleDateString()}
          </p>
        </div>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>

      <Card>
        <h2 className="text-lg font-semibold mb-2">Elo Rating</h2>
        <div className="text-3xl font-bold text-indigo-600">
          {Math.round(hypothesis.elo_rating)}
        </div>
        {hypothesis.tournament_record && (
          <div className="mt-2 text-sm text-gray-600">
            <p>Wins: {hypothesis.tournament_record.wins}</p>
            <p>Losses: {hypothesis.tournament_record.losses}</p>
            <p>Win Rate: {(hypothesis.tournament_record.win_rate * 100).toFixed(1)}%</p>
          </div>
        )}
      </Card>

      <Card>
        <h2 className="text-lg font-semibold mb-2">Summary</h2>
        <p className="text-gray-700 whitespace-pre-wrap">{hypothesis.summary}</p>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold mb-2">Hypothesis Statement</h2>
        <p className="text-gray-700 whitespace-pre-wrap">{hypothesis.hypothesis_statement}</p>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold mb-2">Rationale</h2>
        <p className="text-gray-700 whitespace-pre-wrap">{hypothesis.rationale}</p>
      </Card>

      {hypothesis.reviews && hypothesis.reviews.length > 0 && (
        <Card>
          <h2 className="text-lg font-semibold mb-4">Reviews</h2>
          <div className="space-y-4">
            {hypothesis.reviews.map((review, index) => (
              <div key={review.id} className="border-b pb-4 last:border-b-0">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-medium text-gray-700">Review #{index + 1}</span>
                  <span className="text-sm text-gray-500">
                    Quality Score: {review.quality_score}/10
                  </span>
                </div>
                {review.strengths.length > 0 && (
                  <div className="mb-2">
                    <h4 className="text-sm font-medium text-green-700 mb-1">Strengths:</h4>
                    <ul className="list-disc list-inside text-sm text-gray-700">
                      {review.strengths.map((strength, i) => (
                        <li key={i}>{strength}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {review.weaknesses.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-red-700 mb-1">Weaknesses:</h4>
                    <ul className="list-disc list-inside text-sm text-gray-700">
                      {review.weaknesses.map((weakness, i) => (
                        <li key={i}>{weakness}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {hypothesis.evolution_history && hypothesis.evolution_history.length > 0 && (
        <Card>
          <h2 className="text-lg font-semibold mb-4">Evolution History</h2>
          <div className="space-y-2">
            {hypothesis.evolution_history.map((evolved, index) => (
              <div key={evolved.id} className="text-sm text-gray-700">
                <span className="font-medium">Generation {index + 1}:</span> {evolved.title}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
