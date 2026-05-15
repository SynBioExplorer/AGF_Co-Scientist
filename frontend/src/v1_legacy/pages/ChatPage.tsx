import React, { useState } from 'react';
import { ChatWindow } from '../components/chat/ChatWindow';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { createGoal } from '../services/api';
import { useGoalStore } from '../store/goalStore';

export const ChatPage: React.FC = () => {
  const { activeGoalId, setActiveGoal, clearActiveGoal } = useGoalStore();
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreateGoal = async () => {
    if (!description.trim()) return;

    setLoading(true);
    try {
      const result = await createGoal({
        description: description.trim(),
        constraints: [],
        preferences: [],
      });
      setActiveGoal(result.goal_id, description.trim());
      setDescription('');
    } catch (error) {
      console.error('Failed to create goal:', error);
      alert('Failed to create research goal. Please check your settings and try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!activeGoalId) {
    return (
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Start a Research Session</h1>
        <Card>
          <h2 className="text-lg font-semibold mb-4">Create Research Goal</h2>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe your research question or goal... (e.g., 'Investigate novel approaches to CRISPR gene editing for cancer therapy')"
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 min-h-32"
          />
          <Button
            onClick={handleCreateGoal}
            disabled={loading || !description.trim()}
            className="mt-4 w-full"
          >
            {loading ? 'Creating...' : 'Start Research Session'}
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Research Session</h1>
        <Button variant="secondary" onClick={() => clearActiveGoal()}>
          New Session
        </Button>
      </div>
      <ChatWindow goalId={activeGoalId} />
    </div>
  );
};
