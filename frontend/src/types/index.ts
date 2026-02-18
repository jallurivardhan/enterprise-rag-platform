/** TypeScript type definitions for the Enterprise RAG Platform */

export interface SourceMetadata {
  source_file: string;
  page_number?: number;
  chunk_index: number;
  document_id?: string;
  filename?: string;
}

export interface Source {
  id: string;
  content: string;
  metadata: SourceMetadata;
  score: number;
}

export interface TrustScore {
  grounding_score: number;
  confidence: number;
  is_grounded: boolean;
  is_valid: boolean;
  hallucination_risk: 'low' | 'medium' | 'high';
  issues: string[];
  check_results: Record<string, boolean>;
}

export interface CostInfo {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  model: string;
}

export interface ReasoningStep {
  step_number: number;
  action: 'analyze' | 'decompose' | 'retrieve' | 'synthesize' | 'verify' | 'complete';
  thought: string;
  result?: string;
  sub_query?: string;
  chunks_found?: number;
}

export interface QueryClassification {
  complexity: 'simple' | 'complex';
  confidence: number;
  recommended_mode: 'normal' | 'agentic';
  reasoning: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: Date;
  feedback?: 'up' | 'down';
  trust?: TrustScore;
  cost?: CostInfo;
  mode_used?: 'normal' | 'agentic';
  reasoning_steps?: ReasoningStep[];
  classification?: QueryClassification;
  sub_queries?: string[];
}

export interface UploadResponse {
  success: boolean;
  document_id: string;
  chunks_created: number;
  filename?: string;
}

export interface Document {
  id: string;
  filename: string;
  chunks_count: number;
  created_at: string;
  permission?: 'public' | 'private';
}

export interface ChatRequest {
  query: string;
  conversation_id?: string;
  mode?: 'normal' | 'agentic' | 'auto';
}

export interface ChatResponse {
  answer: string;
  sources: Array<{
    document_id: string;
    filename: string;
    chunk_index: number;
    score: number;
  }>;
  conversation_id: string;
  trust?: TrustScore;
  cost?: CostInfo;
  mode_used: string;
  reasoning_steps?: ReasoningStep[];
  classification?: QueryClassification;
  sub_queries?: string[];
}
