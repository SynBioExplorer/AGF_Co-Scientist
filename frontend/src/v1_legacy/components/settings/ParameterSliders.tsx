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
          <span className="font-medium text-gray-700">Tournament Debate Rounds</span>
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
        <p className="text-xs text-gray-500 mt-1">
          Number of debate turns per top-of-bracket match (paper default: 3)
        </p>
      </div>

      <div>
        <label className="flex justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">Elo K-Factor</span>
          <span className="font-mono text-gray-600">{settings.eloKFactor}</span>
        </label>
        <input
          type="range"
          min="8"
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

      <div>
        <label className="flex justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">Budget (AUD)</span>
          <span className="font-mono text-gray-600">${settings.budgetAud.toFixed(0)}</span>
        </label>
        <input
          type="range"
          min="0"
          max="500"
          step="5"
          value={settings.budgetAud}
          onChange={(e) => settings.setBudgetAud(parseFloat(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
        <p className="text-xs text-gray-500 mt-1">
          Hard cap on LLM spend per run. 0 disables enforcement.
        </p>
      </div>

      <div>
        <label className="flex justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">Safety Threshold</span>
          <span className="font-mono text-gray-600">{settings.safetyThreshold.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={settings.safetyThreshold}
          onChange={(e) => settings.setSafetyThreshold(parseFloat(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
        <p className="text-xs text-gray-500 mt-1">
          Minimum safety score for hypotheses. 0 disables review; 0.5 is typical for production.
        </p>
      </div>

      <div>
        <label className="flex justify-between text-sm mb-1">
          <span className="font-medium text-gray-700">LLM Timeout (s)</span>
          <span className="font-mono text-gray-600">{settings.llmTimeoutSeconds}</span>
        </label>
        <input
          type="range"
          min="30"
          max="900"
          step="30"
          value={settings.llmTimeoutSeconds}
          onChange={(e) => settings.setLlmTimeoutSeconds(parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
        />
        <p className="text-xs text-gray-500 mt-1">
          Per-LLM-call timeout. Increase for complex reasoning models.
        </p>
      </div>
    </div>
  );
};
