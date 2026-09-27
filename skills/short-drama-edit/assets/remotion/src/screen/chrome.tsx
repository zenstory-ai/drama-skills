import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { typedLength } from "../rules.mjs";
import { COLOURS, RARITY, SANS, entrance, rarityOf, unit } from "./tokens";
import { Rarity } from "../schema";

/** Pieces the system-style panels share: frame, header, typewriter, reward rows. */

const useU = (): number => unit(useVideoConfig().height);

const Corners: React.FC<{ colour: string }> = ({ colour }) => {
  const u = useU();
  const length = u * 2.2;
  const weight = Math.max(3, u * 0.28);
  const edge = `${weight}px solid ${colour}`;
  const corner = (style: React.CSSProperties) => (
    <div style={{ position: "absolute", width: length, height: length, ...style }} />
  );
  return (
    <>
      {corner({ top: -weight, left: -weight, borderTop: edge, borderLeft: edge })}
      {corner({ top: -weight, right: -weight, borderTop: edge, borderRight: edge })}
      {corner({ bottom: -weight, left: -weight, borderBottom: edge, borderLeft: edge })}
      {corner({ bottom: -weight, right: -weight, borderBottom: edge, borderRight: edge })}
    </>
  );
};

/** Dark-navy glass with a glowing border, L-shaped corner brackets and moving scanlines. */
export const Frame: React.FC<{
  colour: string;
  width: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ colour, width, children, style }) => {
  const u = useU();
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "relative",
        width,
        padding: `${u * 2.2}px ${u * 2.6}px`,
        background: "linear-gradient(170deg, rgba(10,30,60,0.80), rgba(6,16,36,0.86))",
        border: `${Math.max(2, u * 0.12)}px solid ${colour}aa`,
        boxShadow: `0 0 ${u * 1.6}px ${colour}88, inset 0 0 ${u * 3}px ${colour}22`,
        fontFamily: SANS,
        color: COLOURS.panelInk,
        ...style,
      }}
    >
      <Corners colour={colour} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          backgroundImage: `repeating-linear-gradient(0deg, ${colour}14 0px, ${colour}14 2px, transparent 2px, transparent 5px)`,
          backgroundPositionY: `${frame * 1.5}px`,
        }}
      />
      {children}
    </div>
  );
};

/** 【系统提示】-style header: a diamond, the label, and a rule fading out to the right. */
export const Header: React.FC<{ text: string; colour: string }> = ({ text, colour }) => {
  const u = useU();
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: u * 0.8,
        fontSize: u * 1.9,
        fontWeight: 700,
        color: colour,
        letterSpacing: u * 0.35,
        marginBottom: u * 0.8,
      }}
    >
      <span
        style={{
          width: u * 0.9,
          height: u * 0.9,
          background: colour,
          transform: "rotate(45deg)",
          boxShadow: `0 0 ${u}px ${colour}`,
        }}
      />
      {text}
      <span style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${colour}aa, transparent)` }} />
    </div>
  );
};

/** Typewriter at 35 ms a character from `delay`, with a blinking bar while it types. */
export const Typed: React.FC<{ text: string; delay?: number; style?: React.CSSProperties }> = ({
  text,
  delay = 0,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const chars = Array.from(text);
  const shown = typedLength(frame / fps, delay);
  const typing = shown < chars.length;
  return (
    <div style={style}>
      {chars.slice(0, shown).join("")}
      <span
        style={{
          display: "inline-block",
          width: "0.12em",
          height: "0.9em",
          marginLeft: "0.08em",
          background: "currentColor",
          opacity: typing && Math.floor(frame / 6) % 2 === 0 ? 1 : 0,
        }}
      />
    </div>
  );
};

/** A reward row: rarity chip and name in the rarity's colour, flashing as it arrives. */
export const Reward: React.FC<{ name: string; rarity: Rarity | null; delay: number }> = ({
  name,
  rarity,
  delay,
}) => {
  const u = useU();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const arrived = entrance(frame, fps, delay, 12);
  const label = rarityOf(rarity);
  const colour = RARITY[label];
  const flash = interpolate(frame / fps - delay, [0, 0.12, 0.4], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: u * 1.2,
        margin: `${u * 0.7}px 0`,
        opacity: arrived,
        transform: `translateX(${(1 - arrived) * u * 5}px)`,
      }}
    >
      <span
        style={{
          fontSize: u * 1.5,
          fontWeight: 700,
          color: COLOURS.ink,
          background: colour,
          padding: `${u * 0.15}px ${u * 0.7}px`,
          boxShadow: `0 0 ${u * (0.6 + flash)}px ${colour}`,
        }}
      >
        {label}
      </span>
      <span style={{ fontSize: u * 2.7, fontWeight: 900, color: colour, textShadow: `0 0 ${u * (0.5 + 1.5 * flash)}px ${colour}` }}>
        {name}
      </span>
    </div>
  );
};

/** A compact reward tag for the task panel. */
export const RewardTag: React.FC<{ name: string; rarity: Rarity | null; delay: number }> = ({
  name,
  rarity,
  delay,
}) => {
  const u = useU();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const colour = RARITY[rarityOf(rarity)];
  return (
    <span
      style={{
        fontSize: u * 1.9,
        fontWeight: 700,
        color: colour,
        opacity: entrance(frame, fps, delay),
        border: `1px solid ${colour}88`,
        padding: `${u * 0.2}px ${u * 0.7}px`,
        background: `${colour}14`,
      }}
    >
      {name}
    </span>
  );
};
