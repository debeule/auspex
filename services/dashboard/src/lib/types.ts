export interface DirectSignal {
  event_id: string;
  source_type: string;
  title: string;
  summary: string;
  confidence_score: number;
  published_at: string;
}

export interface CorroboratedSignal {
  entity_key: string;
  distinct_source_types: string[];
  corroborated_at: string;
  confidence: number;
  participant_event_ids: string[];
}

export interface TickerSignalsResponse {
  ticker: string;
  direct_signals: DirectSignal[];
  corroborated_signals: CorroboratedSignal[];
}
