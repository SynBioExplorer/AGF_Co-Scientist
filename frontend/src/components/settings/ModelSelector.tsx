import React from 'react';
import { GOOGLE_MODELS, OPENAI_MODELS } from '../../constants/models';

interface Props {
  provider: 'google' | 'openai';
  model: string;
  onProviderChange: (provider: 'google' | 'openai') => void;
  onModelChange: (model: string) => void;
}

export const ModelSelector: React.FC<Props> = ({
  provider,
  model,
  onProviderChange,
  onModelChange,
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

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
        <select
          value={provider}
          onChange={(e) => onProviderChange(e.target.value as 'google' | 'openai')}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="google">Google (Gemini)</option>
          <option value="openai">OpenAI (GPT)</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
        <select
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
    </div>
  );
};
