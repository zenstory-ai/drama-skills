export type CueKind = "line" | "vo" | "system";

export type Cue = {
  /** Output-time seconds, measured from the rendered segments. */
  start: number;
  end: number;
  /** One on-screen line of a 剧本.md line in its burned form. */
  text: string;
  /** Dialogue, an inner or narrating voice, or the system's voice -- read from 剧本.md. */
  kind: CueKind;
  /** Words to highlight, each occurring in `text`. */
  keys: string[];
};

export type ScreenTextStyle = "card" | "system" | "task" | "corner";
export type Rarity = "传说" | "史诗" | "稀有";

export type ScreenText = {
  /** Output-time seconds. */
  start: number;
  end: number;
  style: ScreenTextStyle;
  /** Rows or items, each traced to a [画面文字] line in 剧本.md. */
  items: { text: string; rarity: Rarity | null }[];
  /** Seconds left at `start`, already resolved for 「接续」; null when nothing counts down. */
  countdown: number | null;
};

export type OverlayProps = {
  cues: Cue[];
  screenTexts: ScreenText[];
  width: number;
  height: number;
  fps: number;
  durationInSeconds: number;
};

export const defaultProps: OverlayProps = {
  cues: [],
  screenTexts: [],
  width: 1080,
  height: 1920,
  fps: 30,
  durationInSeconds: 1,
};
