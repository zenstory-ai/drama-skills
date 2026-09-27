import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { COLOURS, PANEL_TOP_U, StyleProps, TABULAR, entrance, exit, unit } from "./tokens";

/** "微博 2" → ["微博", "2"]: the last word of a row is its value, set to the right. */
const splitRow = (row: string): [string, string] => {
  const found = row.match(/^(.*\S)[\s　]+(\S+)$/);
  return found ? [found[1], found[2]] : [row, ""];
};

/** A light UI card, one row per item — an account list, a leaderboard line. */
export const Card: React.FC<StyleProps> = ({ text, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps);
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: u * PANEL_TOP_U, opacity: exit(frame, fps, text) }}>
      <div
        style={{
          width: width * 0.78,
          background: COLOURS.cardSurface,
          borderRadius: u * 1.4,
          boxShadow: `0 ${u}px ${u * 3}px rgba(0,0,0,0.45)`,
          padding: `${u * 1.4}px ${u * 2.2}px`,
          transform: `scale(${0.9 + 0.1 * shown})`,
          opacity: shown,
          fontFamily,
        }}
      >
        {text.items.map((row, index) => {
          const [label, value] = splitRow(row);
          const arrived = entrance(frame, fps, 0.12 + index * 0.1);
          return (
            <div
              key={index}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: u * 2,
                borderTop: index ? `1px solid ${COLOURS.cardRule}` : "none",
                padding: `${u}px 0`,
                opacity: arrived,
                transform: `translateX(${(1 - arrived) * u * 3}px)`,
              }}
            >
              <span style={{ fontSize: u * 2.4, color: COLOURS.cardTitle, fontWeight: 600 }}>{label}</span>
              <span style={{ ...TABULAR, fontSize: u * 3.2, color: COLOURS.cardValue, fontWeight: 800 }}>{value}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
