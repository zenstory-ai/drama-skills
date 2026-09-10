import { Config } from "@remotion/cli/config";

// The overlay is composited onto untouched picture, so it must carry alpha.
Config.setVideoImageFormat("png");
Config.setPixelFormat("yuva420p");
Config.setCodec("vp8");
