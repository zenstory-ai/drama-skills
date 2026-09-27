import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { COLOURS, MONO, SANS, StyleProps, TOP_U, entrance, exit, unit } from "./tokens";

/**
 * "微博 2" → name 微博, value 2; "微博 粉丝 2" adds 粉丝 as a small unit before
 * the value. A row with one word is all name.
 */
const splitRow = (row: string): { name: string; unit: string; value: string } => {
  const words = row.split(/[\s　]+/).filter(Boolean);
  if (words.length < 2) return { name: row, unit: "", value: "" };
  return { name: words[0], unit: words.slice(1, -1).join(" "), value: words[words.length - 1] };
};

/** A clean app dashboard card: white, rounded, a coloured dot per row, big red numbers. */
export const Card: React.FC<StyleProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps, 0, 15);
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: u * TOP_U.card, opacity: exit(frame, fps, text, 0.15) }}>
      <div
        style={{
          width: width * 0.8,
          background: COLOURS.cardSurface,
          borderRadius: u * 1.6,
          boxShadow: `0 ${u}px ${u * 4}px rgba(0,0,0,0.5)`,
          padding: `${u * 0.7}px ${u * 2.2}px`,
          fontFamily: SANS,
          transform: `translateY(${(1 - shown) * u * 4}px) scale(${0.94 + 0.06 * shown})`,
          opacity: shown,
        }}
      >
        {text.items.map((item, index) => {
          const row = splitRow(item.text);
          return (
            <div
              key={index}
              style={{
                display: "flex",
                alignItems: "center",
                gap: u * 1.2,
                padding: `${u * 1.1}px 0`,
                borderTop: index ? `1px solid ${COLOURS.cardRule}` : "none",
                opacity: entrance(frame, fps, 0.08 + index * 0.07),
              }}
            >
              <span
                style={{
                  width: u * 3,
                  height: u * 3,
                  borderRadius: "50%",
                  background: COLOURS.cardDots[index % COLOURS.cardDots.length],
                }}
              />
              <span style={{ flex: 1, fontSize: u * 2.5, fontWeight: 700, color: COLOURS.cardName }}>{row.name}</span>
              {row.unit ? (
                <span style={{ fontSize: u * 1.7, fontWeight: 700, color: COLOURS.cardUnit, marginRight: u * 0.6 }}>
                  {row.unit}
                </span>
              ) : null}
              <span style={{ fontFamily: MONO, fontSize: u * 3.6, fontWeight: 800, color: COLOURS.cardValue }}>
                {row.value}
              </span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
