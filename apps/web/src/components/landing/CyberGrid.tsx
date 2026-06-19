"use client";

import React, { useEffect, useRef } from "react";

interface Node {
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  size: number;
  pulseSpeed: number;
  pulsePhase: number;
  glowColor: string;
}

interface Connection {
  from: Node;
  to: Node;
  active: boolean;
}

interface Packet {
  connection: Connection;
  progress: number;
  speed: number;
  color: string;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  alpha: number;
  decay: number;
}

export default function CyberGrid() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    // Grid sizing
    const gridSize = 60;

    // Nodes, connections, packets, and particles
    const nodes: Node[] = [];
    const connections: Connection[] = [];
    const packets: Packet[] = [];
    const particles: Particle[] = [];

    // Initialize random nodes in grid intersections
    const cols = Math.floor(width / gridSize) + 2;
    const rows = Math.floor(height / gridSize) + 2;

    const colors = ["rgba(0, 240, 255, 0.4)", "rgba(94, 210, 156, 0.4)"];

    for (let c = 1; c < cols - 1; c++) {
      for (let r = 1; r < rows - 1; r++) {
        // Only spawn nodes with ~15% probability to keep it clean and minimal
        if (Math.random() < 0.12) {
          const baseX = c * gridSize;
          const baseY = r * gridSize;
          nodes.push({
            x: baseX + (Math.random() - 0.5) * 30,
            y: baseY + (Math.random() - 0.5) * 30,
            targetX: baseX,
            targetY: baseY,
            size: Math.random() * 2 + 1.5,
            pulseSpeed: 0.02 + Math.random() * 0.03,
            pulsePhase: Math.random() * Math.PI * 2,
            glowColor: colors[Math.floor(Math.random() * colors.length)],
          });
        }
      }
    }

    // Connect close nodes
    for (let i = 0; i < nodes.length; i++) {
      let connectionsCount = 0;
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // Connect if close enough and haven't exceeded max connections
        if (dist < 150 && connectionsCount < 2) {
          connections.push({
            from: nodes[i],
            to: nodes[j],
            active: true,
          });
          connectionsCount++;
        }
      }
    }

    // Create background floating particles (dust)
    const particleCount = 40;
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: -Math.random() * 0.4 - 0.1, // Float upward
        size: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.6 + 0.1,
        decay: 0.0005 + Math.random() * 0.001,
      });
    }

    // Handle resizing
    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    // Animation Loop
    let tick = 0;
    const animate = () => {
      tick++;
      ctx.clearRect(0, 0, width, height);

      // 1. Draw static grid lines (faint)
      ctx.strokeStyle = "rgba(255, 255, 255, 0.015)";
      ctx.lineWidth = 1;

      // Draw horizontal lines
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Draw vertical lines
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }

      // 2. Draw connections (network topology lines)
      connections.forEach((conn) => {
        ctx.strokeStyle = "rgba(255, 255, 255, 0.02)";
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(conn.from.x, conn.from.y);
        ctx.lineTo(conn.to.x, conn.to.y);
        ctx.stroke();

        // Very faint neon trace occasionally
        if (Math.random() < 0.0005) {
          ctx.strokeStyle = conn.from.glowColor;
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
      });

      // 3. Spawn packets on active connections
      if (connections.length > 0 && Math.random() < 0.08 && packets.length < 25) {
        const conn = connections[Math.floor(Math.random() * connections.length)];
        packets.push({
          connection: conn,
          progress: 0,
          speed: 0.004 + Math.random() * 0.008,
          color: conn.from.glowColor.replace("0.4", "0.9"), // Brighter packet glow
        });
      }

      // 4. Update and draw packets (live traffic pulses)
      for (let i = packets.length - 1; i >= 0; i--) {
        const p = packets[i];
        p.progress += p.speed;

        if (p.progress >= 1) {
          // Remove packet when it reaches the destination
          packets.splice(i, 1);
          continue;
        }

        const startX = p.connection.from.x;
        const startY = p.connection.from.y;
        const endX = p.connection.to.x;
        const endY = p.connection.to.y;

        const currentX = startX + (endX - startX) * p.progress;
        const currentY = startY + (endY - startY) * p.progress;

        // Draw packet pulse
        const radGlow = ctx.createRadialGradient(currentX, currentY, 0, currentX, currentY, 6);
        radGlow.addColorStop(0, "#ffffff");
        radGlow.addColorStop(0.3, p.color);
        radGlow.addColorStop(1, "transparent");

        ctx.fillStyle = radGlow;
        ctx.beginPath();
        ctx.arc(currentX, currentY, 6, 0, Math.PI * 2);
        ctx.fill();

        // Mini trail
        const trailX = startX + (endX - startX) * Math.max(0, p.progress - 0.08);
        const trailY = startY + (endY - startY) * Math.max(0, p.progress - 0.08);
        ctx.strokeStyle = p.color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(trailX, trailY);
        ctx.lineTo(currentX, currentY);
        ctx.stroke();
      }

      // 5. Update and draw nodes
      nodes.forEach((node) => {
        node.pulsePhase += node.pulseSpeed;
        const pulse = Math.sin(node.pulsePhase) * 1.5;
        const currentSize = node.size + pulse;

        // Subtle node drift
        node.x = node.targetX + Math.sin(tick * 0.005 + node.pulsePhase) * 4;
        node.y = node.targetY + Math.cos(tick * 0.005 + node.pulsePhase) * 4;

        // Glowing aura
        ctx.fillStyle = node.glowColor;
        ctx.beginPath();
        ctx.arc(node.x, node.y, currentSize * 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Node center core
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(node.x, node.y, currentSize * 0.8, 0, Math.PI * 2);
        ctx.fill();
      });

      // 6. Update and draw floating dust particles
      particles.forEach((p) => {
        p.y += p.vy;
        p.x += p.vx;
        p.alpha -= p.decay;

        // Wrap around screen or respawn if invisible
        if (p.y < 0 || p.alpha <= 0 || p.x < 0 || p.x > width) {
          p.y = height + 10;
          p.x = Math.random() * width;
          p.vx = (Math.random() - 0.5) * 0.3;
          p.vy = -Math.random() * 0.4 - 0.1;
          p.alpha = Math.random() * 0.6 + 0.1;
        }

        ctx.fillStyle = `rgba(255, 255, 255, ${p.alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden z-0 bg-[#060816]">
      {/* HTML5 Canvas Background for network node simulation */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />

      {/* Thin grid lines at 25%, 50%, and 75% opacity white/5 */}
      <div className="absolute inset-0 flex justify-between pointer-events-none z-10 px-8 lg:px-16">
        <div className="w-[1px] h-full bg-white/5 opacity-25" style={{ left: '25%', position: 'absolute' }}></div>
        <div className="w-[1px] h-full bg-white/5 opacity-50" style={{ left: '50%', position: 'absolute' }}></div>
        <div className="w-[1px] h-full bg-white/5 opacity-25" style={{ left: '75%', position: 'absolute' }}></div>
      </div>

      {/* Faint horizontal pattern grid overlay */}
      <div className="absolute inset-0 grid-lines-h pointer-events-none opacity-40 z-5" />

      {/* Cyber Noise Overlay */}
      <div className="noise-overlay" />

      {/* Central SVG Ellipse Glow centered behind the hero text */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] sm:w-[900px] h-[350px] sm:h-[500px] pointer-events-none z-1 overflow-visible">
        {/* Animated pulse cyan + emerald glow SVG */}
        <svg
          viewBox="0 0 1000 600"
          className="w-full h-full animate-pulse-glow"
          style={{ transformOrigin: "center" }}
        >
          <defs>
            <radialGradient id="heroGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#00f0ff" stopOpacity="0.22" />
              <stop offset="35%" stopColor="#5ed29c" stopOpacity="0.10" />
              <stop offset="70%" stopColor="#060816" stopOpacity="0" />
            </radialGradient>
          </defs>
          <ellipse cx="500" cy="300" rx="420" ry="220" fill="url(#heroGlow)" filter="blur(30px)" />
        </svg>
      </div>

      {/* Ambient gradient overlay panels for layout readability */}
      {/* Left to right dark gradient */}
      <div className="absolute inset-y-0 left-0 w-[50%] bg-gradient-to-r from-[#060816] via-[#060816]/75 to-transparent pointer-events-none z-5" />
      {/* Bottom gradient fade */}
      <div className="absolute bottom-0 inset-x-0 h-[30%] bg-gradient-to-t from-[#060816] to-transparent pointer-events-none z-5" />
      {/* Top gradient fade */}
      <div className="absolute top-0 inset-x-0 h-[15%] bg-gradient-to-b from-[#060816] to-transparent pointer-events-none z-5" />
    </div>
  );
}
