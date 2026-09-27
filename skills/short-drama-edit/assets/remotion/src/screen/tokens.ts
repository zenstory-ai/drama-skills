import React from "react";
import { interpolate, spring } from "remotion";
import { ScreenText } from "../schema";

/**
 * Shared look for every screen-text style. Sizes are in `u`, one hundredth of
 * frame height, so the same numbers hold for 720×1280 and 1080×1920.
 */
export const unit = (height: number): number => height / 100;

/** Every style component takes exactly this, so one can replace another. */
export type StyleProps = { text: ScreenText; fontFamily: string };

/** Where the panels sit: below the platform's top bar, above the faces. */
export const PANEL_TOP_U = 10;
export const CORNER_INSET_U = 4;

export const COLOURS = {
  cardSurface: "rgba(248,249,251,0.96)",
  cardTitle: "#1c2230",
  cardRule: "#e3e6ec",
  cardValue: "#e2372b",
  panelInk: "#eaf6ff",
  systemAccent: "rgba(90,210,255,0.95)",
  systemScan: "rgba(90,210,255,1)",
  taskAccent: "rgba(255,120,90,0.95)",
  taskScan: "rgba(255,140,110,1)",
  taskClock: "#ff6b57",
  bullet: "#ffd66b",
  chipSurface: "rgba(10,14,26,0.72)",
  chipInk: "#ff7a66",
  chipLabel: "#ffb39e",
};

const ENTER = { damping: 16, stiffness: 180, mass: 0.7 };
const EXIT_SECONDS = 0.25;

/** 0→1 entry, `delay` seconds after the piece's first frame. A pure function of the frame. */
export const entrance = (frame: number, fps: number, delay = 0): number =>
  spring({ frame: frame - delay * fps, fps, config: ENTER });

/** 1→0 over the piece's last quarter second. */
export const exit = (frame: number, fps: number, text: ScreenText): number => {
  const length = (text.end - text.start) * fps;
  return interpolate(frame, [length - EXIT_SECONDS * fps, length], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};

/** Digits that do not jitter while a countdown ticks, in the same family as the text. */
export const TABULAR: React.CSSProperties = { fontVariantNumeric: "tabular-nums" };

export const glass = (u: number, accent: string, fontFamily: string): React.CSSProperties => ({
  background: "linear-gradient(160deg, rgba(8,20,40,0.82), rgba(4,10,24,0.88))",
  border: `${Math.max(2, u * 0.18)}px solid ${accent}`,
  borderRadius: u * 1.2,
  boxShadow: `0 0 ${u * 2.5}px ${accent}, inset 0 0 ${u * 2}px rgba(80,200,255,0.15)`,
  padding: `${u * 2}px ${u * 2.4}px`,
  fontFamily,
  color: COLOURS.panelInk,
  position: "relative",
  overflow: "hidden",
});

/** A soft band sweeping down the panel, driven by the frame alone. */
export const scanBand = (frame: number, fps: number, accent: string): React.CSSProperties => ({
  position: "absolute",
  left: 0,
  right: 0,
  top: `${(((frame / fps) * 55) % 130) - 15}%`,
  height: "12%",
  background: `linear-gradient(180deg, transparent, ${accent}33, transparent)`,
  pointerEvents: "none",
});
