import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { COLOURS, PANEL_TOP_U, StyleProps, entrance, exit, glass, scanBand, unit } from "./tokens";

/** A glowing system panel: the first item is the status line, the rest arrive one by one. */
export const SystemPanel: React.FC<StyleProps> = ({ text, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps);
  // A brief flicker on arrival, stepped on even frames so it is the same every render.
  const flicker = frame < 0.3 * fps && Math.floor(frame / 2) % 2 ? 0.55 : 1;
  const [status, ...items] = text.items;
  return (
    <AbsoluteFill
      style={{ alignItems: "center", paddingTop: u * PANEL_TOP_U, opacity: exit(frame, fps, text) * flicker }}
    >
      <div
        style={{
          ...glass(u, COLOURS.systemAccent, fontFamily),
          width: width * 0.8,
          transform: `scaleY(${0.2 + 0.8 * shown})`,
          opacity: shown,
        }}
      >
        <div style={scanBand(frame, fps, COLOURS.systemScan)} />
        <div
          style={{
            fontSize: u * 4,
            fontWeight: 800,
            marginBottom: items.length ? u * 1.4 : 0,
            textShadow: `0 0 ${u * 1.2}px ${COLOURS.systemAccent}`,
          }}
        >
          {status}
        </div>
        {items.map((item, index) => {
          const arrived = entrance(frame, fps, 0.35 + index * 0.22);
          return (
            <div
              key={index}
              style={{
                display: "flex",
                alignItems: "center",
                gap: u,
                margin: `${u * 0.7}px 0`,
                opacity: arrived,
                transform: `translateX(${(1 - arrived) * u * 4}px)`,
              }}
            >
              <span style={{ color: COLOURS.bullet, fontSize: u * 2.2 }}>✦</span>
              <span style={{ fontSize: u * 2.6, fontWeight: 700 }}>{item}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
