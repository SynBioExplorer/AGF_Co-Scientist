import React from 'react';
import type { AgentType, AgentModelConfig } from '../../types';
import { GOOGLE_MODELS, OPENAI_MODELS, AGENT_DESCRIPTIONS } from '../../constants/models';

interface Props {
  provider: 'google' | 'openai';
  agentType: AgentType;
  config: AgentModelConfig;
  onConfigChange: (agentType: AgentType, config: AgentModelConfig) => void;
}

export const AgentModelConfigComponent: React.FC<Props> = ({
  provider,
  agentType,
  config,
  onConfigChange,
}) => {
  const models = provider === 'google' ? GOOGLE_MODELS : OPENAI_MODELS;

  // Group models by category
  const groupedModels = models.reduce((acc, model) => {
    if (!acc[model.category]) {
      acc[model.category] = [];
    }
    acc[model.category].push(model);
    return acc;
  }, {} as Record<string, typeof models>);

  const agentLabel = agentType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-3">
      <div>
        <h4 className="font-medium text-gray-900">{agentLabel}</h4>
        <p className="text-xs text-gray-500 mt-1">{AGENT_DESCRIPTIONS[agentType]}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
          <select
            value={config.model}
            onChange={(e) =>
              onConfigChange(agentType, { ...config, model: e.target.value })
            }
            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {Object.entries(groupedModels).map(([category, categoryModels]) => (
              <optgroup key={category} label={category}>
                {categoryModels.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Temperature: {config.temperature.toFixed(1)}
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={config.temperature}
            onChange={(e) =>
              onConfigChange(agentType, {
                ...config,
                temperature: parseFloat(e.target.value),
              })
            }
            className="w-full"
          />
        </div>
      </div>
    </div>
  );
};
