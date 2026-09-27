import { interpolate, spring } from "remotion";
import { CueKind, Rarity, ScreenText } from "../schema";

/**
 * Shared look for subtitles and every screen-text style. Sizes are in `u`, one
 * hundredth of frame height, so the same numbers hold for 720×1280 and 1080×1920.
 */
export const unit = (height: number): number => height / 100;

/** Every style component takes exactly this, so one can replace another. */
export type StyleProps = { text: ScreenText };

export const SANS = '"Noto Sans SC", sans-serif';
export const MONO = '"JetBrains Mono", "Noto Sans SC", monospace';

export const COLOURS = {
  system: "#3FE0FF",
  task: "#FF8A5B",
  taskTitle: "#FFE3D6",
  alarm: "#FF5A4E",
  chipLabel: "#FFB39E",
  panelInk: "#EAF7FF",
  muted: "#9FB7CC",
  ink: "#0B1020",
  cardSurface: "rgba(255,255,255,0.97)",
  cardName: "#1C2230",
  cardUnit: "#9AA3B2",
  cardRule: "#EEF0F4",
  cardValue: "#E5322D",
  cardDots: ["#FF4D4F", "#1FA2FF", "#111111", "#2BB673"],
};

/** Subtitle fill by who speaks; the same values are in edit_tool.py for the ASS route. */
export const SUBTITLE: { fill: Record<CueKind, string>; keyword: string; rim: string } = {
  fill: { line: "#FFFFFF", vo: "#9FE8FF", system: "#3FE0FF" },
  keyword: "#FFD400",
  rim: "#0B0D12",
};

/** Unmarked items read as 稀有. */
export const RARITY: Record<Rarity, string> = { 传说: "#FFC940", 史诗: "#B26BFF", 稀有: "#3FA9FF" };
export const rarityOf = (rarity: Rarity | null): Rarity => rarity ?? "稀有";

/** Where each style sits, in `u` from the top. */
export const TOP_U = { card: 16, system: 10, task: 9, corner: 5.5 };

/** 0→1 entry, `delay` seconds after the piece's first frame. A pure function of the frame. */
export const entrance = (frame: number, fps: number, delay = 0, damping = 14): number =>
  spring({ frame: frame - delay * fps, fps, config: { damping, stiffness: 200, mass: 0.6 } });

/** 1→0 over the piece's last `seconds`; the caller also lifts by (1 − value). */
export const exit = (frame: number, fps: number, text: ScreenText, seconds = 0.22): number => {
  const length = (text.end - text.start) * fps;
  return interpolate(frame, [length - seconds * fps, length], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};

/** Two or three frames of glitch before a panel settles. */
export const glitch = (frame: number): { opacity: number; dx: number } =>
  frame > 3 ? { opacity: 1, dx: 0 } : { opacity: frame % 2 ? 0.35 : 1, dx: frame % 2 ? 6 : -4 };
