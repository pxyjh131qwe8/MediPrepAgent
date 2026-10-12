export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface ConsultRequest {
  symptoms: string
  age?: number
  gender?: string
  duration?: string
  medical_history?: string
  medication_history?: string
  allergy_history?: string
  goal?: string
  thread_id: string
  use_saved_context: boolean
}

export interface RiskResult {
  risk_level: RiskLevel
  warnings: string[]
  action: string
  matched_signals: string[]
  negated_signals: string[]
}

export interface EvidenceItem {
  source: string
  title: string
  excerpt: string
  relevance: number
}

export interface AgentTraceStep {
  agent: string
  role: string
  status: 'completed' | 'limited' | 'corrected'
  summary: string
}

export interface ConsultResponse {
  summary: string
  possible_causes: string[]
  risk_result: RiskResult
  department_result: {
    primary_department: string
    alternative_departments: string[]
    reason: string
  }
  pre_visit_checklist: string[]
  lifestyle_advice: string[]
  references: string[]
  disclaimer: string
  evidence: EvidenceItem[]
  follow_up_questions: string[]
  agent_trace: AgentTraceStep[]
  quality: {
    evidence_status: 'grounded' | 'limited' | 'unavailable'
    safety_reviewed: boolean
    limitations: string[]
  }
}

export interface ConsultationTurn {
  id: string
  request: ConsultRequest
  response: ConsultResponse
}
