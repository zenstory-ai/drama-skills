import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { Frame, Header, Reward, Typed } from "./chrome";
import { COLOURS, StyleProps, TOP_U, entrance, exit, glitch, unit } from "./tokens";

const TYPE_DELAY = 0.15;

/**
 * 【系统提示】: the first item types out as the status line, the rest arrive as
 * rarity-coloured reward rows once it has finished.
 */
export const SystemPanel: React.FC<StyleProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps, 0, 13);
  const jitter = glitch(frame);
  const leaving = exit(frame, fps, text);
  const [status, ...rewards] = text.items;
  const rewardsFrom = TYPE_DELAY + Array.from(status.text).length * 0.035 + 0.15;
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: u * TOP_U.system, opacity: leaving * jitter.opacity }}>
      <div style={{ transform: `translate(${jitter.dx}px, ${(1 - leaving) * -u * 2}px) scale(${0.9 + 0.1 * shown})` }}>
        <Frame colour={COLOURS.system} width={width * 0.82}>
          <Header text="【系统提示】" colour={COLOURS.system} />
          <Typed
            text={status.text}
            delay={TYPE_DELAY}
            style={{
              fontSize: u * 4.4,
              fontWeight: 900,
              letterSpacing: u * 0.3,
              textShadow: `0 0 ${u * 1.4}px ${COLOURS.system}`,
              margin: `${u * 0.4}px 0 ${rewards.length ? u * 1.2 : 0}px`,
            }}
          />
          {rewards.map((item, index) => (
            <Reward key={index} name={item.text} rarity={item.rarity} delay={rewardsFrom + index * 0.28} />
          ))}
        </Frame>
      </div>
    </AbsoluteFill>
  );
};
