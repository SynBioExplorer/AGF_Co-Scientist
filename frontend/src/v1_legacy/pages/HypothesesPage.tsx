import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHypotheses, getHypothesisDetail } from '../services/api';
import { HypothesisList } from '../components/hypotheses/HypothesisList';
import { HypothesisDetail } from '../components/hypotheses/HypothesisDetail';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useGoalStore } from '../store/goalStore';
import type { Hypothesis, HypothesisDetail as HypothesisDetailType } from '../types';

export const HypothesesPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeGoalId } = useGoalStore();
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [selectedHypothesis, setSelectedHypothesis] = useState<HypothesisDetailType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadHypotheses = async () => {
      if (!activeGoalId) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const result = await getHypotheses(activeGoalId, 1, 100);
        setHypotheses(result.hypotheses || []);
      } catch (error) {
        console.error('Failed to load hypotheses:', error);
      } finally {
        setLoading(false);
      }
    };

    loadHypotheses();
  }, [activeGoalId]);

  const handleSelectHypothesis = async (id: string) => {
    try {
      const detail = await getHypothesisDetail(id);
      // API returns { hypothesis, reviews, tournament_record, evolution_history }
      // Flatten into the HypothesisDetailType shape
      setSelectedHypothesis({
        ...detail.hypothesis,
        reviews: detail.reviews || [],
        tournament_record: detail.tournament_record || { wins: 0, losses: 0, win_rate: 0, total_matches: 0 },
        evolution_history: detail.evolution_history || [],
      });
    } catch (error) {
      console.error('Failed to load hypothesis detail:', error);
    }
  };

  if (!activeGoalId && !loading) {
    return (
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Hypotheses</h1>
        <Card>
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">
              No active research session. Start by creating a research goal.
            </p>
            <Button onClick={() => navigate('/chat')}>
              Start Research Session
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Hypotheses</h1>

      {selectedHypothesis ? (
        <HypothesisDetail
          hypothesis={selectedHypothesis}
          onClose={() => setSelectedHypothesis(null)}
        />
      ) : (
        <HypothesisList
          hypotheses={hypotheses}
          loading={loading}
          onSelectHypothesis={handleSelectHypothesis}
        />
      )}
    </div>
  );
};
