export type Cue = {
  /** Output-time seconds, measured from the rendered segments. */
  start: number;
  end: number;
  /** The line as written in 剧本.md. Never a transcription. */
  text: string;
};

export type SubtitleProps = {
  cues: Cue[];
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

export const defaultProps: SubtitleProps = {
  cues: [],
  width: 1080,
  height: 1920,
  fps: 24,
  durationInSeconds: 1,
  fontScale: 0.034,
  bottomScale: 0.055,
  fontFamily:
    '"PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif',
};
