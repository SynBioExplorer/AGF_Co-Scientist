import React from 'react';
import { useSettingsStore } from '../../store/settingsStore';

export const ParameterSliders: React.FC = () => {
  const settings = useSettingsStore();

  return (
    <div className="space-y-4">
      <div>
        <label className="flex justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">Max Iterations</span>
          <span className="font-mono text-gray-600">{settings.maxIterations}</span>
        </label>
        <input
          type="range"
          min="1"
          max="50"
          step="1"
          value={settings.maxIterations}
          onChange={(e) => settings.setMaxIterations(parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
      </div>

      <div>
        <label className="flex justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">Tournament Rounds</span>
          <span className="font-mono text-gray-600">{settings.tournamentRounds}</span>
        </label>
        <input
          type="range"
          min="1"
          max="10"
          step="1"
          value={settings.tournamentRounds}
          onChange={(e) => settings.setTournamentRounds(parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
      </div>

      <div>
        <label className="flex justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">Elo K-Factor</span>
          <span className="font-mono text-gray-600">{settings.eloKFactor}</span>
        </label>
        <input
          type="range"
          min="16"
          max="64"
          step="4"
          value={settings.eloKFactor}
          onChange={(e) => settings.setEloKFactor(parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
        <p className="text-xs text-gray-500 mt-1">
          Higher = ratings change faster after matches
        </p>
      </div>
    </div>
  );
};
