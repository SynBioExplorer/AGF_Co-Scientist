export type ProviderId = 'gemini' | 'openai' | 'deepseek' | 'anthropic';

export interface ProviderMeta {
  id: ProviderId;
  label: string;
  brandColor: string;
  helpUrl: string;
}

export const PROVIDERS: ProviderMeta[] = [
  {
    id: 'gemini',
    label: 'Google Gemini',
    brandColor: '#4285F4',
    helpUrl: 'https://aistudio.google.com/app/apikey',
  },
  {
    id: 'openai',
    label: 'OpenAI (GPT)',
    brandColor: '#10A37F',
    helpUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    brandColor: '#5468E7',
    helpUrl: 'https://platform.deepseek.com/api_keys',
  },
  {
    id: 'anthropic',
    label: 'Anthropic (Claude)',
    brandColor: '#D97757',
    helpUrl: 'https://console.anthropic.com/settings/keys',
  },
];

export type AgentType =
  | 'generation'
  | 'reflection'
  | 'ranking'
  | 'evolution'
  | 'proximity'
  | 'meta_review'
  | 'supervisor'
  | 'safety';

export const AGENT_TYPES: AgentType[] = [
  'generation',
  'reflection',
  'ranking',
  'evolution',
  'proximity',
  'meta_review',
  'supervisor',
  'safety',
];

export interface AgentModelConfig {
  provider: ProviderId | 'default';
  model: string;
  temperature: number;
}

export interface AgentModelsResponse {
  default: { provider: ProviderId; model: string; temperature: number };
  agents: Record<AgentType, AgentModelConfig | null>;
}

export interface ValidateKeyResponse {
  valid: boolean;
  error?: string;
  available_models?: string[];
}

export interface SetupStatus {
  completed: boolean;
  missing_steps: string[];
}

export interface ProviderSecretState {
  set: boolean;
  masked: string;
}

export interface SecretsResponse {
  providers: Record<ProviderId, ProviderSecretState>;
  optional: {
    tavily: ProviderSecretState;
    semantic_scholar: { enabled: boolean };
    pubmed: ProviderSecretState;
  };
  email: { enabled: boolean; recipient: string };
  export_folder: string;
}

export interface SetupCompletePayload {
  providers: Partial<Record<ProviderId, string>>;
  optional: {
    tavily?: string;
    semantic_scholar?: boolean;
    pubmed?: string;
  };
  export_folder: string;
  email: { enabled: boolean; recipient?: string };
}

export interface Hypothesis {
  id: string;
  title: string;
  summary: string;
  elo_rating: number;
  status?: string;
  rank?: number;
}

export type RunStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface RunSummary {
  id: string;
  goal: string;
  status: RunStatus;
  iteration?: number;
  max_iterations?: number;
  hypotheses_count?: number;
  created_at: string;
  finished_at?: string;
  cost_usd?: number;
}

export interface RunDetail extends RunSummary {
  constraints?: string[];
  preferences?: string[];
  current_phase?:
    | 'generation'
    | 'reflection'
    | 'ranking'
    | 'evolution'
    | 'meta_review'
    | 'idle';
  hypotheses?: Hypothesis[];
  tournament?: TournamentBracketData;
  logs?: LogEntry[];
  stats?: RunStats;
  html_report_path?: string;
}

export interface RunStats {
  duration_seconds?: number;
  hypotheses_generated?: number;
  matches_played?: number;
  cost_usd?: number;
  cost_aud?: number;
}

export interface LogEntry {
  ts: string;
  level: 'info' | 'warn' | 'error';
  message: string;
}

export interface TournamentMatch {
  id: string;
  round: number;
  a?: Hypothesis;
  b?: Hypothesis;
  winner_id?: string;
}

export interface TournamentBracketData {
  rounds: TournamentMatch[][];
}

export interface CreateRunPayload {
  goal: {
    description: string;
    constraints: string[];
    preferences: string[];
  };
}

export interface MailtoExport {
  mailto_url: string;
  html_report_path: string;
}
