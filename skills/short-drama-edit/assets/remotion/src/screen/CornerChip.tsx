import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { formatCountdown, secondsLeft } from "../rules.mjs";
import { COLOURS, CORNER_INSET_U, StyleProps, TABULAR, entrance, exit, unit } from "./tokens";

/** A small top-right chip: a label, and the countdown when there is one. */
export const CornerChip: React.FC<StyleProps> = ({ text, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps);
  return (
    <AbsoluteFill
      style={{
        alignItems: "flex-end",
        paddingTop: u * CORNER_INSET_U,
        paddingRight: u * 2.2,
        opacity: exit(frame, fps, text),
      }}
    >
      <div
        style={{
          ...TABULAR,
          fontFamily,
          fontSize: u * 2.1,
          fontWeight: 800,
          color: COLOURS.chipInk,
          background: COLOURS.chipSurface,
          border: `1px solid ${COLOURS.taskAccent}`,
          borderRadius: u * 0.8,
          padding: `${u * 0.5}px ${u * 1.1}px`,
          boxShadow: `0 0 ${u}px rgba(255,120,90,0.55)`,
          opacity: shown,
          transform: `translateY(${(1 - shown) * -u * 2}px)`,
        }}
      >
        <span style={{ fontSize: u * 1.5, color: COLOURS.chipLabel, marginRight: u * 0.6 }}>
          {text.items.join(" ")}
        </span>
        {text.countdown === null ? null : formatCountdown(secondsLeft(text.countdown, frame / fps))}
      </div>
    </AbsoluteFill>
  );
};
