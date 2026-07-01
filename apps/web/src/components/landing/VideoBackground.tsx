"use client";

import { useEffect, useRef } from "react";
import type Hls from "hls.js";

export default function VideoBackground() {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let hls: Hls | null = null;
    let disposed = false;
    const streamUrl = "https://stream.mux.com/tLkHO1qZoaaQOUeVWo8hEBeGQfySP02EPS02BmnNFyXys.m3u8";

    const initHls = async () => {
      // Dynamically import hls.js to avoid SSR issues
      const { default: Hls } = await import("hls.js");

      if (disposed) return;

      if (Hls.isSupported()) {
        hls = new Hls({
          enableWorker: false, // Required parameter
        });
        hls.loadSource(streamUrl);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          video.play().catch((err) => {
            console.log("Autoplay blocked by browser. Retrying muted...", err);
          });
        });
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        // Native fallback (Safari)
        video.src = streamUrl;
      }
    };

    initHls();

    return () => {
      disposed = true;
      hls?.destroy();
    };
  }, []);

  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none overflow-hidden z-0 bg-bg-dark-navy">
      {/* Cinematic Fullscreen Animated Video Background */}
      <video
        ref={videoRef}
        autoPlay
        muted
        loop
        playsInline
        suppressHydrationWarning
        className="w-full h-full object-cover opacity-45 blur-[3px] scale-105"
      />

      {/* Thin vertical grid lines at 25%, 50%, and 75% opacity white/2 (softer) */}
      <div className="absolute inset-0 flex justify-between pointer-events-none z-10 px-8 lg:px-16">
        <div className="absolute left-1/4 w-px h-full bg-white/2" />
        <div className="absolute left-1/2 w-px h-full bg-white/2" />
        <div className="absolute left-3/4 w-px h-full bg-white/2" />
      </div>

      {/* Softer faint horizontal pattern grid overlay */}
      <div className="absolute inset-0 grid-lines-h pointer-events-none opacity-20 z-5" />

      {/* Cyber Noise Overlay */}
      <div className="noise-overlay opacity-[0.012]" />

      {/* Softer Central SVG Ellipse Glow centered behind the hero text */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-150 sm:w-237.5 h-87.5 sm:h-137.5 pointer-events-none z-1 overflow-visible">
        <svg
          viewBox="0 0 1000 600"
          className="w-full h-full animate-pulse-glow origin-center"
        >
          <defs>
            <radialGradient id="heroGlowRefined" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#00f0ff" stopOpacity="0.16" />
              <stop offset="35%" stopColor="#5ed29c" stopOpacity="0.08" />
              <stop offset="70%" stopColor="#060816" stopOpacity="0" />
            </radialGradient>
          </defs>
          <ellipse cx="500" cy="300" rx="450" ry="240" fill="url(#heroGlowRefined)" filter="blur(35px)" />
        </svg>
      </div>

      {/* Cinematic gradient overlays for legibility */}
      {/* Left dark gradient (#060816 to transparent) */}
      <div className="absolute inset-y-0 left-0 w-[55%] bg-linear-to-r from-bg-dark-navy via-bg-dark-navy/70 to-transparent pointer-events-none z-5" />
      {/* Bottom fade overlay */}
      <div className="absolute bottom-0 inset-x-0 h-[35%] bg-linear-to-t from-bg-dark-navy to-transparent pointer-events-none z-5" />
      {/* Top fade overlay */}
      <div className="absolute top-0 inset-x-0 h-[20%] bg-linear-to-b from-bg-dark-navy to-transparent pointer-events-none z-5" />
    </div>
  );
}
