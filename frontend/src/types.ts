export interface Profile {
  goal: string; skill_level: string; primary_stroke: string; distance: string
  pace_context: string; breathing: string; environment: string; camera_angle: string
  pain: string; known_issues: string[]; coach_notes: string
}
export interface Settings {
  model: string; temperature: number; image_detail: 'auto' | 'low' | 'high'
  max_frames: number; smart_frames: boolean; pose_enabled: boolean; include_media_on_followup: boolean
}
export interface Analysis {
  analysis_category: string
  stroke_id: { label: string; confidence_pct: number }
  visibility: { can_see: string[]; cannot_see: string[] }
  top_3_priorities: { rank: number; problem: string; likely_cause: string; cue: string }[]
  drills: { name: string; how: string; why: string }[]
  what_to_film_next: { angle: string; distance: string }[]
  pose_metrics: string[] | null
}
export interface Message { role: 'user' | 'assistant'; content: string }
export interface Session {
  profile: Profile; category: string
  media: { name: string; type: 'image' | 'video'; duration: number; frame_count: number; frames: string[] } | null
  analysis: Analysis | null; analysis_markdown: string; chat_messages: Message[]
  pose_metrics: string[]; pose_warning: string; annotated_frames: string[]
}
export interface Config {
  categories: Record<string, string>; models: string[]; max_upload_mb: number
  max_video_seconds: number; image_extensions: string[]; video_extensions: string[]; api_key_configured: boolean
}
export const defaultProfile: Profile = {
  goal: '', skill_level: 'Intermediate', primary_stroke: '', distance: '', pace_context: 'Unknown',
  breathing: '', environment: 'Pool', camera_angle: '', pain: '', known_issues: [], coach_notes: '',
}
export const defaultSettings: Settings = {
  model: 'gpt-5.6-luna', temperature: 0.6, image_detail: 'auto', max_frames: 10,
  smart_frames: true, pose_enabled: false, include_media_on_followup: false,
}
