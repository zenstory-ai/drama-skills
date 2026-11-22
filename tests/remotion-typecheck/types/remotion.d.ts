declare module "*.css";

declare module "@remotion/cli/config" {
  export const Config: {
    setVideoImageFormat(format: "jpeg" | "png" | "none"): void;
    setPixelFormat(format: string): void;
    setCodec(codec: string): void;
  };
}

declare module "remotion" {
  import type React from "react";

  export type VideoConfig = {
    width: number;
    height: number;
    fps: number;
    durationInFrames: number;
    id: string;
  };

  export type SpringConfig = {
    damping?: number;
    mass?: number;
    stiffness?: number;
    overshootClamping?: boolean;
  };

  export type InterpolateOptions = {
    extrapolateLeft?: "extend" | "clamp" | "identity" | "wrap";
    extrapolateRight?: "extend" | "clamp" | "identity" | "wrap";
    easing?: (input: number) => number;
  };

  export type CalculateMetadataFunction<Props> = (options: {
    props: Props;
    defaultProps: Props;
    abortSignal: AbortSignal;
    compositionId: string;
  }) =>
    | Partial<Pick<VideoConfig, "durationInFrames" | "fps" | "width" | "height">> & {
        props?: Props;
      }
    | Promise<
        Partial<Pick<VideoConfig, "durationInFrames" | "fps" | "width" | "height">> & {
          props?: Props;
        }
      >;

  export const AbsoluteFill: React.FC<{
    style?: React.CSSProperties;
    className?: string;
    children?: React.ReactNode;
  }>;

  export const Sequence: React.FC<{
    from?: number;
    durationInFrames?: number;
    layout?: "absolute-fill" | "none";
    name?: string;
    children?: React.ReactNode;
  }>;

  export function Composition<Props extends Record<string, unknown>>(props: {
    id: string;
    component: React.ComponentType<Props>;
    defaultProps?: Props;
    durationInFrames: number;
    fps: number;
    width: number;
    height: number;
    calculateMetadata?: CalculateMetadataFunction<Props>;
  }): React.ReactElement | null;

  export function registerRoot(component: React.ComponentType): void;
  export function useCurrentFrame(): number;
  export function useVideoConfig(): VideoConfig;
  export function delayRender(label?: string): number;
  export function continueRender(handle: number): void;
  export function cancelRender(error: unknown): void;
  export function spring(options: {
    frame: number;
    fps: number;
    config?: SpringConfig;
    from?: number;
    to?: number;
    durationInFrames?: number;
    durationRestThreshold?: number;
    delay?: number;
  }): number;
  export function interpolate(
    input: number,
    inputRange: readonly number[],
    outputRange: readonly number[],
    options?: InterpolateOptions,
  ): number;
}
