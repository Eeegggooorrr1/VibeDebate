export interface Debate {
  id: string;
  topic_title: string;
  user_position: string;
  opponent_position: string;
  status: string;
  created_at: string;
  chats?: Chat[];
}
export interface Chat {
  id: string;
  debate_id: string;
  side: "attack" | "defense";
  title: string;
  description: string;
  seed_claim: string;
  attack_hint?: string | null;
  opponent_persona_id: string;
  difficulty: number;
  status: string;
}
export interface Message {
  id: string;
  chat_id: string;
  sequence_no: number;
  role: string;
  content: string;
  generation_status: string;
  client_request_id: string | null;
}
export interface Topic {
  id: string;
  title: string;
  description: string;
  default_positions: string[];
}
export interface Persona {
  id: string;
  name: string;
  description: string;
  available_difficulties: number[];
}
export interface Category {
  id: string;
  name: string;
}

export interface ChatSuggestion {
  title: string;
  description: string;
  seed_claim: string;
  hint: string | null;
}
export interface AnalysisIssue {
  type: string;
  severity: "low" | "medium" | "high";
  evidence_quote: string;
  explanation: string;
  improvement: string;
  confidence: number;
}
export interface MessageAnalysis {
  message_id: string;
  status: "pending" | "running" | "completed" | "failed";
  is_substantive: boolean | null;
  overall_score: number | null;
  confidence: number | null;
  dimensions: {
    key: string;
    score: number | null;
    applicable: boolean;
    explanation: string;
  }[];
  strengths: string[];
  conduct_flags: string[];
  issues: AnalysisIssue[];
  next_step: string | null;
}
