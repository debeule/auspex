export interface DirectSignal {
  event_id: string;
  source_type: string;
  title: string;
  summary: string;
  confidence_score: number;
  published_at: string;
}

/** A live ticker record: two independent sources naming this ticker's company (COR-019). */
export interface CorroboratedSignal {
  entity_key: string;
  ticker: string;
  distinct_source_types: string[];
  episode_opened_at: string;
  corroborated_at: string;
  confidence: number;
  participant_event_ids: string[];
}

/** An entity record listing one of the ticker's signals with no ticker record; no score. */
export interface ContextCorroboration {
  entity_key: string;
  reason: 'broad_entity' | 'no_independent_pair_for_ticker';
  distinct_source_types: string[];
  episode_opened_at: string;
  corroborated_at: string;
  participant_event_ids: string[];
}

export interface TickerSignalsResponse {
  ticker: string;
  direct_signals: DirectSignal[];
  corroborated_signals: CorroboratedSignal[];
  context_corroborations: ContextCorroboration[];
}

export interface WatchlistGeneTarget {
  gene_target: string;
  source: 'graph' | 'clinicaltrials' | 'manual';
}

export interface WatchlistEntry {
  id: string;
  ticker: string;
  company_name: string;
  added_at: string;
  gene_targets: WatchlistGeneTarget[];
}

export interface GeneTargetWithCount {
  name: string;
  signal_count: number;
}

export interface CtSuggestion {
  term: string;
  type: 'condition' | 'intervention';
}

export interface WatchlistPreview {
  ticker: string;
  company_name: string | null;
  graph_gene_targets: GeneTargetWithCount[];
  ct_suggestions: CtSuggestion[];
}

export interface WatchlistGeneTargetStat {
  name: string;
  source: string;
  signal_count: number;
  last_seen: string | null;
}

export interface CorroborationRef {
  entity_key: string;
  corroborated_at: string;
  confidence: number;
}

export interface WatchlistStats {
  total_direct: number;
  total_corroborations: number;
  most_active_gene_target: string | null;
  last_signal_at: string | null;
}

export interface WatchlistSummary {
  ticker: string;
  company_name: string;
  gene_targets: WatchlistGeneTargetStat[];
  direct_signals: DirectSignal[];
  corroborations: CorroborationRef[];
  stats: WatchlistStats;
}
