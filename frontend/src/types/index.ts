export interface ResearchGoal {
  id: string;
  description: string;
  constraints: string[];
  preferences: string[];
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
}

export interface Hypothesis {
  id: string;
  research_goal_id: string;
  title: string;
  summary: string;
  hypothesis_statement: string;
  rationale: string;
  elo_rating: number;
  status: string;
  created_at: string;
}

export interface Review {
  id: string;
  hypothesis_id: string;
  quality_score: number;
  strengths: string[];
  weaknesses: string[];
  review_type: string;
}

export interface TournamentRecord {
  wins: number;
  losses: number;
  win_rate: number;
  total_matches: number;
}

export interface ChatMessage {
  id: string;
  role: 'scientist' | 'assistant';
  content: string;
  timestamp: string;
}

export interface SystemStatistics {
  goal_id: string;
  hypotheses_generated: number;
  hypotheses_pending_review: number;
  hypotheses_in_tournament: number;
  total_matches: number;
  tournament_convergence: number;
}

export interface HypothesisDetail extends Hypothesis {
  reviews: Review[];
  tournament_record: TournamentRecord;
  evolution_history: Hypothesis[];
}

export type AgentType =
  | 'generation'
  | 'reflection'
  | 'ranking'
  | 'evolution'
  | 'proximity'
  | 'meta_review'
  | 'supervisor'
  | 'safety';

export interface AgentModelConfig {
  model: string;
  temperature: number;
}

export interface Settings {
  // Model selection - per agent type
  llmProvider: 'google' | 'openai';

  // Per-agent model configuration
  agentModels: Record<AgentType, AgentModelConfig>;

  // Default fallback model
  defaultModel: string;
  defaultTemperature: number;

  // API keys (stored in localStorage)
  googleApiKey: string;
  openaiApiKey: string;
  tavilyApiKey: string;

  // Parameters
  maxIterations: number;
  tournamentRounds: number;
  eloKFactor: number;

  // Feature toggles
  enableEvolution: boolean;
  enableWebSearch: boolean;
  enableLiteratureSearch: boolean;
}
