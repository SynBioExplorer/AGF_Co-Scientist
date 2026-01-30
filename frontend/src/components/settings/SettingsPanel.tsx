import React, { useState } from 'react';
import { useSettingsStore } from '../../store/settingsStore';
import { ModelSelector } from './ModelSelector';
import { AgentModelConfigComponent } from './AgentModelConfig';
import { ApiKeyInput } from './ApiKeyInput';
import { ParameterSliders } from './ParameterSliders';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import type { AgentType } from '../../types';

const AGENT_TYPES: AgentType[] = [
  'generation',
  'reflection',
  'ranking',
  'evolution',
  'proximity',
  'meta_review',
  'supervisor',
  'safety',
];

export const SettingsPanel: React.FC = () => {
  const settings = useSettingsStore();
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className="space-y-6">
      <Card>
        <h3 className="text-lg font-semibold mb-4">Model Configuration</h3>
        <ModelSelector
          provider={settings.llmProvider}
          model={settings.defaultModel}
          onProviderChange={settings.setProvider}
          onModelChange={settings.setDefaultModel}
        />

        <div className="mt-4 pt-4 border-t border-gray-200">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
          >
            {showAdvanced ? '− Hide' : '+ Show'} Per-Agent Configuration
          </button>
        </div>
      </Card>

      {showAdvanced && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Per-Agent Model Configuration</h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={settings.resetAgentModelsToDefaults}
            >
              Reset to Defaults
            </Button>
          </div>

          <div className="space-y-4">
            {AGENT_TYPES.map((agentType) => (
              <AgentModelConfigComponent
                key={agentType}
                provider={settings.llmProvider}
                agentType={agentType}
                config={settings.agentModels[agentType]}
                onConfigChange={settings.setAgentModel}
              />
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h3 className="text-lg font-semibold mb-4">API Keys</h3>
        <div className="space-y-3">
          <ApiKeyInput
            label="Google API Key"
            value={settings.googleApiKey}
            onChange={settings.setGoogleApiKey}
          />
          <ApiKeyInput
            label="OpenAI API Key"
            value={settings.openaiApiKey}
            onChange={settings.setOpenaiApiKey}
          />
          <ApiKeyInput
            label="Anthropic API Key"
            value={settings.anthropicApiKey}
            onChange={settings.setAnthropicApiKey}
          />
          <ApiKeyInput
            label="Tavily API Key"
            value={settings.tavilyApiKey}
            onChange={settings.setTavilyApiKey}
          />
          <ApiKeyInput
            label="PubMed API Key"
            value={settings.pubmedApiKey}
            onChange={settings.setPubmedApiKey}
          />
          <ApiKeyInput
            label="LangSmith API Key"
            value={settings.langsmithApiKey}
            onChange={settings.setLangsmithApiKey}
          />
        </div>
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4">Parameters</h3>
        <ParameterSliders />
      </Card>

      <Card>
        <h3 className="text-lg font-semibold mb-4">Feature Toggles</h3>
        <div className="space-y-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enableEvolution}
              onChange={(e) => settings.setEnableEvolution(e.target.checked)}
              className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
            />
            <span className="text-gray-700">Enable Hypothesis Evolution</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enableWebSearch}
              onChange={(e) => settings.setEnableWebSearch(e.target.checked)}
              className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
            />
            <span className="text-gray-700">Enable Web Search</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.enableLiteratureSearch}
              onChange={(e) => settings.setEnableLiteratureSearch(e.target.checked)}
              className="w-4 h-4 text-indigo-600 rounded focus:ring-indigo-500"
            />
            <span className="text-gray-700">Enable Literature Search</span>
          </label>
        </div>
      </Card>
    </div>
  );
};
