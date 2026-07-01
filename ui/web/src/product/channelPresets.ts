export const LANGUAGE_PRESETS = [
  "English",
  "German",
  "Persian",
  "Turkish",
  "Arabic",
  "Custom",
] as const;

export const TONE_PRESETS = [
  "cinematic",
  "documentary",
  "educational",
  "mysterious",
  "horror",
  "motivational",
  "calm/relaxing",
  "luxury",
  "funny",
  "custom",
] as const;

export const VISUAL_STYLE_PRESETS = [
  "cinematic realistic",
  "nature documentary",
  "dark mystery",
  "soft relaxing",
  "product ad",
  "educational explainer",
  "anime-inspired",
  "papercraft",
  "custom",
] as const;

export const PROVIDER_PRESETS = [
  { id: "runway", label: "Runway" },
  { id: "hailuo", label: "Hailuo" },
  { id: "auto", label: "Auto" },
] as const;

export const NARRATION_PRESETS = [
  { id: "disabled", label: "Disabled" },
  { id: "elevenlabs", label: "ElevenLabs" },
] as const;

export const MUSIC_PRESETS = [
  { id: "none", label: "None" },
  { id: "local_mp3", label: "Local MP3" },
  { id: "suno_future_placeholder", label: "Suno (coming soon)" },
] as const;

export const WIZARD_TOPIC_EXAMPLES = [
  "Relaxing nature facts",
  "Scorpions and desert animals",
  "AI tools for beginners",
  "Self-care for women",
  "Fishing education",
] as const;
