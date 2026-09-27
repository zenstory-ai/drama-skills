export type Cue = {
  /** Output-time seconds, measured from the rendered segments. */
  start: number;
  end: number;
  /** The burned form of the 剧本.md line: closing punctuation dropped, pauses as spaces. */
  text: string;
};

export type ScreenTextStyle = "card" | "system" | "task" | "corner";

export type ScreenText = {
  /** Output-time seconds. */
  start: number;
  end: number;
  style: ScreenTextStyle;
  /** Rows or items, each traced to a [画面文字] line in 剧本.md. */
  items: string[];
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
  /** Type size as a fraction of frame height, so one number survives any delivery. */
  fontScale: number;
  /** Distance from the bottom edge, also a fraction of frame height. */
  bottomScale: number;
  fontFamily: string;
};

export type SubtitleProps = Pick<OverlayProps, "cues" | "fontScale" | "bottomScale" | "fontFamily">;

export const defaultProps: OverlayProps = {
  cues: [],
  screenTexts: [],
  width: 1080,
  height: 1920,
  fps: 24,
  durationInSeconds: 1,
  fontScale: 0.034,
  bottomScale: 0.055,
  fontFamily:
    '"PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
};
