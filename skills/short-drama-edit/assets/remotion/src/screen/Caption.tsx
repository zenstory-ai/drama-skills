import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { COLOURS, SANS, StyleProps, TOP_U, entrance, exit, unit } from "./tokens";

/** Clean, borderless caption card for locations, timestamps, titles, and narrative notes. */
export const Caption: React.FC<StyleProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps, 0, 18);
  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        paddingTop: u * TOP_U.caption,
        opacity: exit(frame, fps, text, 0.18),
      }}
    >
      <div
        style={{
          maxWidth: width * 0.84,
          background: COLOURS.captionSurface,
          borderRadius: u * 0.9,
          boxShadow: `0 ${u * 0.6}px ${u * 2.4}px rgba(0,0,0,0.38)`,
          padding: `${u * 1.1}px ${u * 2.4}px`,
          fontFamily: SANS,
          textAlign: "center",
          transform: `translateY(${(1 - shown) * u * 2.2}px)`,
          opacity: shown,
        }}
      >
        {text.items.map((item, index) => (
          <div
            key={index}
            style={{
              fontSize: index === 0 ? u * 2.8 : u * 2.1,
              fontWeight: index === 0 ? 900 : 700,
              letterSpacing: `${u * 0.12}px`,
              lineHeight: 1.38,
              color: index === 0 ? COLOURS.captionInk : COLOURS.captionSub,
              marginTop: index === 0 ? 0 : u * 0.45,
              opacity: entrance(frame, fps, index * 0.06, 18),
            }}
          >
            {item.text}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
