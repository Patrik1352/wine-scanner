export interface Wine {
  slug: string
  name: string
  winery_name: string | null
  region: string | null
  category: string | null
  color_category: string | null
  sweetness_from_category: string | null
  grapes: string[]
  description: string | null
  alcohol_percent: number | null
  alcohol_max_percent: number | null
  serving_temperature_c: string | null
  food_pairings: string[]
  public_rating: number | null
  guide_rating: number | null
  image_url: string | null
  source_url: string | null
  fetched_at: string | null
  similar_wine_slugs: string[]
}
export type Recognition =
  | { status: 'matched'; slug: string; low_confidence?: boolean; request_id?: string }
  | { status: 'needs_better_photo' | 'no_confident_match'; slug: null; reason_code: string; request_id?: string }
export type Mode = 'demo' | 'api'
export type DemoScenario = 'matched' | 'ratings' | 'incomplete' | 'low_quality' | 'multiple_bottles' | 'ambiguous_pair' | 'no_confident_match' | 'offline' | 'unavailable'
export interface WineService {
  ready(signal: AbortSignal): Promise<void>
  recognize(file: File, signal: AbortSignal): Promise<Recognition>
  wine(slug: string, signal: AbortSignal): Promise<Wine>
  alternatives(wine: Wine, signal: AbortSignal): Promise<Wine[]>
}
