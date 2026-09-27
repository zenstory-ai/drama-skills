import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { formatCountdown, parseProgress, secondsLeft, sinceTick } from "../rules.mjs";
import { Frame, Header, RewardTag, Typed } from "./chrome";
import { COLOURS, MONO, StyleProps, TOP_U, entrance, exit, glitch, unit } from "./tokens";

/**
 * 【新任务】: title, the goal typed out, reward tags, an `N / M` item as the
 * 进度 line with its bar, and the countdown pulsing on each second.
 */
export const TaskPanel: React.FC<StyleProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const u = unit(height);
  const shown = entrance(frame, fps, 0, 13);
  const jitter = glitch(frame);
  const leaving = exit(frame, fps, text);
  const [title, goal, ...rest] = text.items;
  const progressItem = rest.find((item) => parseProgress(item.text));
  const progress = progressItem ? parseProgress(progressItem.text) : null;
  const rewards = rest.filter((item) => item !== progressItem);
  const elapsed = frame / fps;
  const beat =
    text.countdown === null ? 1 : 1 + 0.05 * Math.max(0, 1 - sinceTick(text.countdown, elapsed) / 0.15);
  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: u * TOP_U.task, opacity: leaving * jitter.opacity }}>
      <div style={{ transform: `translate(${jitter.dx}px, ${(1 - leaving) * -u * 2}px) scale(${0.9 + 0.1 * shown})` }}>
        <Frame colour={COLOURS.task} width={width * 0.86}>
          <Header text="【新任务】" colour={COLOURS.task} />
          <div
            style={{
              fontSize: u * 4.2,
              fontWeight: 900,
              letterSpacing: u * 0.3,
              color: COLOURS.taskTitle,
              textShadow: `0 0 ${u * 1.2}px ${COLOURS.task}`,
              margin: `${u * 0.2}px 0 ${u * 0.8}px`,
            }}
          >
            {title.text}
          </div>
          {goal ? (
            <Typed text={goal.text} delay={0.25} style={{ fontSize: u * 2.35, fontWeight: 700, lineHeight: 1.45 }} />
          ) : null}
          {rewards.length ? (
            <div style={{ marginTop: u * 1.2, display: "flex", flexWrap: "wrap", gap: `${u * 0.6}px ${u}px` }}>
              {rewards.map((item, index) => (
                <RewardTag key={index} name={item.text} rarity={item.rarity} delay={0.5 + index * 0.12} />
              ))}
            </div>
          ) : null}
          {progress && progressItem ? (
            <>
              <div
                style={{
                  marginTop: u * 1.4,
                  fontSize: u * 1.7,
                  fontWeight: 700,
                  color: COLOURS.muted,
                  display: "flex",
                  justifyContent: "space-between",
                }}
              >
                <span>进度</span>
                <span style={{ fontFamily: MONO, fontWeight: 800 }}>{progressItem.text}</span>
              </div>
              <div style={{ height: u * 0.6, background: "#ffffff1c", marginTop: u * 0.4 }}>
                <div
                  style={{
                    // A sliver stays visible at zero, so the bar reads as a bar.
                    width: `${Math.max(1.2, progress.ratio * 100)}%`,
                    height: "100%",
                    background: COLOURS.alarm,
                    boxShadow: `0 0 ${u * 0.6}px ${COLOURS.alarm}`,
                  }}
                />
              </div>
            </>
          ) : null}
          {text.countdown === null ? null : (
            <div
              style={{
                marginTop: u * 1.3,
                fontFamily: MONO,
                fontWeight: 800,
                fontSize: u * 4.2,
                color: COLOURS.alarm,
                textShadow: `0 0 ${u}px ${COLOURS.alarm}`,
                transform: `scale(${beat})`,
                transformOrigin: "left center",
              }}
            >
              {formatCountdown(secondsLeft(text.countdown, elapsed))}
            </div>
          )}
        </Frame>
      </div>
    </AbsoluteFill>
  );
};
