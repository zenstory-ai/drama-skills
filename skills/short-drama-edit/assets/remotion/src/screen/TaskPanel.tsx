import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { formatCountdown, secondsLeft } from "../rules.mjs";
import {
  COLOURS, PANEL_TOP_U, StyleProps, TABULAR, entrance, exit, glass, scanBand, unit,
} from "./tokens";

/** A task panel: title, the terms one per line, and a countdown that really ticks. */
export const TaskPanel: React.FC<StyleProps> = ({ text, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps);
  const [title, ...terms] = text.items;
  const pulse = 0.85 + 0.15 * Math.abs(Math.sin((frame / fps) * Math.PI));
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: u * PANEL_TOP_U, opacity: exit(frame, fps, text) }}>
      <div
        style={{
          ...glass(u, COLOURS.taskAccent, fontFamily),
          width: width * 0.84,
          transform: `translateY(${(1 - shown) * -u * 6}px)`,
          opacity: shown,
        }}
      >
        <div style={scanBand(frame, fps, COLOURS.taskScan)} />
        <div
          style={{
            fontSize: u * 3.8,
            fontWeight: 800,
            marginBottom: u * 1.2,
            textShadow: `0 0 ${u * 1.2}px ${COLOURS.taskAccent}`,
          }}
        >
          {title}
        </div>
        {terms.map((term, index) => (
          <div key={index} style={{ fontSize: u * 2.3, lineHeight: 1.45, fontWeight: 600 }}>
            {term}
          </div>
        ))}
        {text.countdown === null ? null : (
          <div
            style={{
              ...TABULAR,
              marginTop: u * 1.6,
              fontSize: u * 4.4,
              fontWeight: 800,
              color: COLOURS.taskClock,
              opacity: pulse,
              textShadow: `0 0 ${u}px ${COLOURS.taskAccent}`,
            }}
          >
            {formatCountdown(secondsLeft(text.countdown, frame / fps))}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
