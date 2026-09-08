/* ORCA Frontend Types */

export interface AnalysisRequest {
  question: string;
  geometry: GeoJSON.Geometry;
  start_date: string;
  end_date: string;
  variables?: string[];
  fast_ml_mode?: boolean;
}

export interface AnalysisResult {
  analysis_id: string;
  status: string;
  question: string;
  geometry?: GeoJSON.Geometry;
  summary: string;
  confidence: number;
  confidence_level: string;
  ecosystem_status: string;
  observations: Observation[];
  agent_results: AgentResult[];
  agents_used: string[];
  hypotheses: Hypothesis[];
  evidence: EvidenceItem[];
  temporal_relationships: TemporalRelationship[];
  spatial_relationships: string[];
  data_sources: DataSourceInfo[];
  uncertainties: string[];
  processing_time_ms?: number;
  metadata?: Record<string, any>;
}

export interface Observation {
  id: string;
  source: string;
  dataset: string;
  variable: string;
  value: number;
  unit: string;
  latitude: number;
  longitude: number;
  timestamp: string;
  quality: number;
  is_demo: boolean;
}

export interface AgentResult {
  id: string;
  agent_type: string;
  status: string;
  findings: AgentFinding[];
  evidence: Observation[];
  hypotheses: string[];
  confidence: number;
  data_sources_used: string[];
  records_retrieved: number;
  error?: string;
}

export interface AgentFinding {
  id: string;
  variable: string;
  description: string;
  value?: number;
  unit?: string;
  anomaly_detected: boolean;
  anomaly_severity?: string;
}

export interface Hypothesis {
  id: string;
  title: string;
  description: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  score: number;
  confidence_level: string;
  confidence_breakdown?: Record<string, number | null>;
  uncertainty_notes: string[];
}

export interface EvidenceItem {
  id: string;
  source: string;
  dataset: string;
  variable: string;
  value?: number;
  unit?: string;
  agent: string;
  evidence_type: string;
  strength: string;
  description: string;
}

export interface TemporalRelationship {
  event_a: string;
  event_b: string;
  relationship: string;
  time_delta_hours?: number;
  description: string;
}

export interface DataSourceInfo {
  name: string;
  status: string;
  records_used: number;
  variables_covered?: string[];
  message?: string;
}

export interface MapLayer {
  id: string;
  name: string;
  variable: string;
  unit: string;
  color_range: string[];
}

export interface ProviderHealth {
  provider_name: string;
  status: string;
  last_check?: string;
  message?: string;
  datasets_available?: string[];
}

export interface SuitabilityResult {
  candidates: CandidateLocation[];
  top_recommendations: CandidateLocation[];
  overall_data_quality: number;
  data_sources_used: string[];
  uncertainties: string[];
  disclaimer: string;
}

export interface CandidateLocation {
  latitude: number;
  longitude: number;
  label: string;
  suitability_score: number;
  factors: Record<string, number>;
  factor_descriptions: string[];
  data_quality: number;
  data_sources: string[];
  data_freshness: string;
}

export type AgentStatus = 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'NO_DATA';

export const AGENT_ICONS: Record<string, string> = {
  coordinator: '🧠',
  ocean: '🌊',
  satellite: '🛰️',
  biology: '🐋',
  weather: '⛅',
  fisheries: '🐟',
  pollution: '🏭',
  literature: '📚',
};

export const INTENT_LABELS: Record<string, string> = {
  FISHING_LOCATION_RECOMMENDATION: '🎣 Fishing Recommendation',
  ECOSYSTEM_STATUS: '🌍 Ecosystem Status',
  ANOMALY_DETECTION: '⚠️ Anomaly Detection',
  CAUSE_ANALYSIS: '🔍 Cause Analysis',
  REGION_COMPARISON: '📊 Region Comparison',
  TEMPORAL_ANALYSIS: '📈 Temporal Analysis',
  MARINE_CONDITION: '🌊 Marine Conditions',
  SATELLITE_ANALYSIS: '🛰️ Satellite Analysis',
  FISHING_ACTIVITY_ANALYSIS: '🐟 Fishing Activity',
  POLLUTION_ANALYSIS: '🏭 Pollution Analysis',
  GENERAL_MARINE_QUERY: '🔬 General Analysis',
};

export const PIPELINE_LABELS: Record<string, string> = {
  FISHING_RECOMMENDATION: 'Fishing Recommendation Pipeline',
  ANOMALY: 'Anomaly Detection Pipeline',
  CAUSE: 'Cause Analysis Pipeline',
  SIMPLE_DATA: 'Simple Data Query',
  GENERAL: 'General Analysis',
};
