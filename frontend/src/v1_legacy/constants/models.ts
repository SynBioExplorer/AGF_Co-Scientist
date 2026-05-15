export const GOOGLE_MODELS = [
  // Gemini 3 (Latest - Preview)
  { value: 'gemini-3-pro-preview', label: 'Gemini 3 Pro (Preview)', category: '3.0' },
  { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash (Preview)', category: '3.0' },

  // Gemini 2.0 Flash
  { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash (Experimental)', category: '2.0' },
  { value: 'gemini-2.0-flash-thinking-exp-01-21', label: 'Gemini 2.0 Flash Thinking', category: '2.0' },

  // Gemini 1.5 Pro (Recommended for reasoning)
  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro', category: '1.5' },
  { value: 'gemini-1.5-pro-002', label: 'Gemini 1.5 Pro (002)', category: '1.5' },

  // Gemini 1.5 Flash (Fast & efficient)
  { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash', category: '1.5' },
  { value: 'gemini-1.5-flash-002', label: 'Gemini 1.5 Flash (002)', category: '1.5' },
  { value: 'gemini-1.5-flash-8b', label: 'Gemini 1.5 Flash 8B', category: '1.5' },
];

export const OPENAI_MODELS = [
  // GPT-5 (Latest)
  { value: 'gpt-5.2', label: 'GPT-5.2', category: 'gpt-5' },
  { value: 'gpt-5-mini', label: 'GPT-5 Mini', category: 'gpt-5' },
  { value: 'gpt-5-nano', label: 'GPT-5 Nano', category: 'gpt-5' },

  // o-series (Reasoning models)
  { value: 'o3-mini', label: 'o3-mini', category: 'o-series' },
  { value: 'o1', label: 'o1', category: 'o-series' },
  { value: 'o1-mini', label: 'o1-mini', category: 'o-series' },

  // GPT-4o (Latest multimodal)
  { value: 'gpt-4o', label: 'GPT-4o', category: 'gpt-4' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini', category: 'gpt-4' },

  // GPT-4 Turbo
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', category: 'gpt-4' },
  { value: 'gpt-4-turbo-preview', label: 'GPT-4 Turbo Preview', category: 'gpt-4' },

  // GPT-4
  { value: 'gpt-4', label: 'GPT-4', category: 'gpt-4' },

  // GPT-3.5
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', category: 'gpt-3.5' },
];

export const DEFAULT_AGENT_MODELS = {
  google: {
    generation: { model: 'gemini-3-pro-preview', temperature: 0.7 },
    reflection: { model: 'gemini-3-pro-preview', temperature: 0.3 },
    ranking: { model: 'gemini-3-flash-preview', temperature: 0.1 },
    evolution: { model: 'gemini-3-flash-preview', temperature: 0.8 },
    proximity: { model: 'gemini-3-flash-preview', temperature: 0.2 },
    meta_review: { model: 'gemini-3-pro-preview', temperature: 0.4 },
    supervisor: { model: 'gemini-3-flash-preview', temperature: 0.2 },
    safety: { model: 'gemini-3-flash-preview', temperature: 0.1 },
  },
  openai: {
    generation: { model: 'gpt-5.2', temperature: 0.7 },
    reflection: { model: 'gpt-5.2', temperature: 0.3 },
    ranking: { model: 'gpt-5-mini', temperature: 0.1 },
    evolution: { model: 'gpt-5-mini', temperature: 0.8 },
    proximity: { model: 'gpt-5-nano', temperature: 0.2 },
    meta_review: { model: 'gpt-5.2', temperature: 0.4 },
    supervisor: { model: 'gpt-5-mini', temperature: 0.2 },
    safety: { model: 'gpt-5-nano', temperature: 0.1 },
  },
};

export const AGENT_DESCRIPTIONS = {
  generation: 'Generates novel hypotheses from research goals',
  reflection: 'Reviews and critiques hypothesis quality',
  ranking: 'Compares hypotheses in Elo tournaments',
  evolution: 'Evolves hypotheses using 7 strategies',
  proximity: 'Clusters and deduplicates similar hypotheses',
  meta_review: 'Synthesizes reviews into research overviews',
  supervisor: 'Orchestrates workflow and task prioritization',
  safety: 'Validates hypotheses for ethical/safety concerns',
};
