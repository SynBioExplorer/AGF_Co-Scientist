import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHypotheses, getStatistics } from '../services/api';
import { EloChart } from '../components/visualizations/EloChart';
import { QualityDistribution } from '../components/visualizations/QualityDistribution';
import { Card } from '../components/common/Card';
import { Loading } from '../components/common/Loading';
import { Button } from '../components/common/Button';
import { useGoalStore } from '../store/goalStore';
import type { Hypothesis, SystemStatistics } from '../types';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { activeGoalId } = useGoalStore();
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [stats, setStats] = useState<SystemStatistics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      if (!activeGoalId) {
        setLoading(false);
        return;
      }

      try {
        const [hypothesesData, statisticsData] = await Promise.all([
          getHypotheses(activeGoalId, 1, 100),
          getStatistics(activeGoalId),
        ]);
        setHypotheses(hypothesesData.hypotheses || []);
        setStats(statisticsData);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [activeGoalId]);

  if (loading) {
    return <Loading message="Loading dashboard..." />;
  }

  if (!activeGoalId) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
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
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Total Hypotheses</h3>
          <p className="text-3xl font-bold text-indigo-600">
            {stats?.hypotheses_generated || 0}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500 mb-1">In Tournament</h3>
          <p className="text-3xl font-bold text-indigo-600">
            {stats?.hypotheses_in_tournament || 0}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Total Matches</h3>
          <p className="text-3xl font-bold text-indigo-600">
            {stats?.total_matches || 0}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-gray-500 mb-1">Convergence</h3>
          <p className="text-3xl font-bold text-indigo-600">
            {stats?.tournament_convergence ? `${(stats.tournament_convergence * 100).toFixed(0)}%` : 'N/A'}
          </p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EloChart hypotheses={hypotheses} />
        <QualityDistribution hypotheses={hypotheses} />
      </div>

      <Card>
        <h2 className="text-xl font-semibold mb-4">Recent Activity</h2>
        {hypotheses.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No activity yet. Start by creating a research goal in the Chat page.
          </p>
        ) : (
          <div className="space-y-2">
            {hypotheses.slice(0, 5).map((h) => (
              <div key={h.id} className="flex justify-between items-center py-2 border-b">
                <span className="text-gray-700">{h.title}</span>
                <span className="text-sm text-gray-500">
                  {new Date(h.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
