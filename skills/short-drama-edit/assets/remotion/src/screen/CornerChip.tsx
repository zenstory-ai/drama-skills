import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { formatCountdown, secondsLeft } from "../rules.mjs";
import { Frame } from "./chrome";
import { COLOURS, MONO, StyleProps, TOP_U, entrance, exit, unit } from "./tokens";

/** The task chrome in miniature, top right: the label, and the countdown when there is one. */
export const CornerChip: React.FC<StyleProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps);
  return (
    <AbsoluteFill
      style={{ alignItems: "flex-end", paddingTop: u * TOP_U.corner, paddingRight: u * 2.4, opacity: exit(frame, fps, text) }}
    >
      <div style={{ opacity: shown, transform: `translateX(${(1 - shown) * u * 6}px)` }}>
        <Frame colour={COLOURS.task} width={u * 24} style={{ padding: `${u * 0.7}px ${u * 1.1}px` }}>
          <div style={{ fontSize: u * 1.35, color: COLOURS.chipLabel, fontWeight: 700, letterSpacing: u * 0.2 }}>
            {text.items.map((item) => item.text).join(" · ")}
          </div>
          {text.countdown === null ? null : (
            <div
              style={{
                fontFamily: MONO,
                fontWeight: 800,
                fontSize: u * 2.4,
                color: COLOURS.alarm,
                textShadow: `0 0 ${u * 0.4}px ${COLOURS.alarm}`,
              }}
            >
              {formatCountdown(secondsLeft(text.countdown, frame / fps))}
            </div>
          )}
        </Frame>
      </div>
    </AbsoluteFill>
  );
};
