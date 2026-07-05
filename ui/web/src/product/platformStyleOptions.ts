export type PlatformTabId = "youtube_shorts" | "instagram_reels" | "tiktok";

export const PLATFORM_TABS: { id: PlatformTabId; label: string }[] = [
  { id: "youtube_shorts", label: "YouTube" },
  { id: "instagram_reels", label: "Instagram" },
  { id: "tiktok", label: "TikTok" },
];

export const YOUTUBE_STYLE_OPTIONS = [
  { id: "cinematic realistic", label: "Cinematic Realistic" },
  { id: "documentary", label: "Documentary" },
  { id: "animated", label: "Animated" },
  { id: "minimal", label: "Minimal" },
  { id: "dramatic", label: "Dramatic" },
] as const;

export const INSTAGRAM_STYLE_OPTIONS = [
  { id: "aesthetic", label: "Aesthetic" },
  { id: "cinematic", label: "Cinematic" },
  { id: "beauty & lifestyle", label: "Beauty & Lifestyle" },
  { id: "animated", label: "Animated" },
  { id: "colorful vibrant", label: "Colorful Vibrant" },
  { id: "minimalist clean", label: "Minimalist Clean" },
] as const;

export const INSTAGRAM_FILTER_MOOD_OPTIONS = [
  { id: "warm", label: "Warm" },
  { id: "cool", label: "Cool" },
  { id: "neutral", label: "Neutral" },
  { id: "moody", label: "Moody" },
] as const;

export const TIKTOK_STYLE_OPTIONS = [
  { id: "energetic", label: "Energetic" },
  { id: "trendy", label: "Trendy" },
  { id: "raw & authentic", label: "Raw & Authentic" },
  { id: "animated", label: "Animated" },
  { id: "fast cut", label: "Fast Cut" },
  { id: "cinematic", label: "Cinematic" },
] as const;

export const TIKTOK_PACE_OPTIONS = [
  { id: "fast", label: "Fast" },
  { id: "medium", label: "Medium" },
  { id: "slow", label: "Slow" },
] as const;

export const YOUTUBE_DURATION_OPTIONS = [15, 30, 40, 60] as const;
export const INSTAGRAM_DURATION_OPTIONS = [15, 30, 60] as const;
export const TIKTOK_DURATION_OPTIONS = [15, 30, 60] as const;

export type PlatformSettings = {
  youtube_shorts: { style: string; duration: number };
  instagram_reels: { style: string; duration: number; filterMood: string };
  tiktok: { style: string; duration: number; pace: string };
};

export const DEFAULT_PLATFORM_SETTINGS: PlatformSettings = {
  youtube_shorts: { style: "cinematic realistic", duration: 30 },
  instagram_reels: { style: "aesthetic", duration: 30, filterMood: "neutral" },
  tiktok: { style: "energetic", duration: 30, pace: "medium" },
};
