import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface GoalState {
  // Current active goal
  activeGoalId: string | null;
  activeGoalDescription: string | null;

  // Actions
  setActiveGoal: (goalId: string, description: string) => void;
  clearActiveGoal: () => void;
}

export const useGoalStore = create<GoalState>()(
  persist(
    (set) => ({
      // Default values
      activeGoalId: null,
      activeGoalDescription: null,

      // Actions
      setActiveGoal: (goalId, description) =>
        set({ activeGoalId: goalId, activeGoalDescription: description }),
      clearActiveGoal: () =>
        set({ activeGoalId: null, activeGoalDescription: null }),
    }),
    {
      name: 'coscientist-goal',
    }
  )
);
