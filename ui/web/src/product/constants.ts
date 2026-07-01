export const DURATION_PRESETS = [6, 8, 10, 20, 30, 40] as const;

export const KLING_DURATION_PRESETS = [15, 30, 40, 60] as const;

export const KLING_CLIP_HINTS: Record<number, string> = {
  15: "1 clip (12s action + 3s bridge)",
  30: "2 clips (12s action + 3s bridge each)",
  40: "3 clips (12s action + 3s bridge each)",
  60: "4 clips (12s action + 3s bridge each)",
};

export const AUDIO_STRATEGY_OPTIONS = [
  { id: "auto", label: "Auto" },
  { id: "music_only", label: "Music Only" },
  { id: "narrator", label: "Narrator" },
  { id: "kling_native_audio", label: "Kling Native Audio" },
] as const;

export const PROVIDER_OPTIONS = [
  { id: "kling_3_0_pro_native_audio", label: "Kling 3.0 Pro Native Audio" },
  { id: "auto", label: "Auto" },
  { id: "runway", label: "Runway Gen-4" },
  { id: "runway_gen5", label: "Runway Gen-5" },
] as const;

export const DURATION_PRESET_OPTIONS = [
  ...DURATION_PRESETS.map((value) => ({ id: String(value), label: `${value}s` })),
  { id: "custom", label: "Custom" },
] as const;

export const PLATFORM_OPTIONS = [
  { id: "tiktok", label: "TikTok" },
  { id: "instagram_reels", label: "Instagram Reels" },
  { id: "youtube_shorts", label: "YouTube Shorts" },
  { id: "youtube_long", label: "YouTube Long" },
  { id: "multi", label: "Multi-platform" },
] as const;

export const ASPECT_RATIO_OPTIONS = [
  { id: "9:16", label: "9:16 (Vertical)" },
  { id: "16:9", label: "16:9 (Horizontal)" },
] as const;

export const PLATFORM_ASPECT_DEFAULTS: Record<string, string> = {
  tiktok: "9:16",
  instagram_reels: "9:16",
  youtube_shorts: "9:16",
  youtube_long: "16:9",
  multi: "9:16",
};

export function defaultAspectRatioForPlatform(platform: string): string {
  return PLATFORM_ASPECT_DEFAULTS[platform] || "9:16";
}

export const STYLE_OPTIONS = [
  "cinematic",
  "documentary",
  "motivational",
  "horror/mystery",
  "product/ad",
  "custom",
] as const;

export const PIPELINE_STEPS = [
  "Topic",
  "Content Brain",
  "Director",
  "Critic",
  "Runway",
  "Assembly",
  "Publish Package",
] as const;

export const FUTURE_PATCHES = [
  "Auto Upload Patch",
  "Real ElevenLabs Voice Patch",
  "Burned Subtitle Patch",
  "TikTok Upload Patch",
  "YouTube Upload Patch",
  "Instagram Upload Patch",
  "Advanced Calendar Automation Patch",
  "Multi-channel Management Patch",
  "Music/SFX Patch",
  "Suno Music Patch",
] as const;

export type UserNavItem =
  | "dashboard"
  | "create"
  | "schedule"
  | "results"
  | "automation"
  | "upload"
  | "upgrade"
  | "settings"
  | "developer";
