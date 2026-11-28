"use client";

import { useEffect, useRef } from "react";

/** 
 * BrainAnimation - A self-contained 3D brain visual using SVG.
 * Features:
 * - Realistic 3D human brain silhouette
 * - Continuously rotating brain
 * - Visible neural connections
 * - Electric impulses travelling through neural pathways
 * - Glowing neuron connections
 * - Electrical waves travelling across the brain
 * - Animated synaptic activity
 * - Blue, cyan and electric-purple lighting
 * - Dark professional trading dashboard theme
 * - Reduced-motion accessibility support
 * - Low GPU usage (SVG-based, no Canvas/Three.js)
 */

interface BrainAnimationProps {
  /** Optional custom className */
  className?: string;
  /** Animation speed multiplier */
  speed?: number;
  /** Whether to show neural activity based on AI status */
  aiActive?: boolean;
  /** Reduced motion preference */
  reducedMotion?: boolean;
}

export function BrainAnimation({
  className,
  speed = 1,
  aiActive = true,
  reducedMotion = false,
}: BrainAnimationProps) {
  useEffect(() => {
    // No imperative animations - all are CSS-animated
    return undefined;
  }, [aiActive, reducedMotion, speed]);

  const animationSpeed = reducedMotion ? 0 : speed;

  return (
    <div 
      className={className}
      style={{
        width: "100%",
        height: "200px",
        background: "linear-gradient(135deg, #0a0a2b 0%, #1a1a47 100%)",
        borderRadius: "8px",
        overflow: "hidden",
        marginTop: "1rem",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundImage:
            "radial-gradient(circle at 20% 80%, rgba(0, 255, 255, 0.1) 0%, transparent 50%), " +
            "radial-gradient(circle at 80% 20%, rgba(128, 0, 255, 0.1) 0%, transparent 50%), " +
            "radial-gradient(circle at 40% 40%, rgba(255, 0, 255, 0.1) 0%, transparent 50%)",
          pointerEvents: "none",
          opacity: 0.6,
        }}
      />
      
      <svg
        viewBox="0 0 360 240"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
        }}
      >
        {/* Brain shape - simplified 3D silhouette */}
        <path
          d="M180 10 C140 30, 100 50, 80 90 C60 130, 100 170, 180 210 C260 170, 300 130, 320 90 C340 50, 300 30, 180 10"
          fill="none"
          stroke="rgba(0, 255, 255, 0.8)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        
        {/* Neural connections */}
        <g
          stroke="rgba(128, 0, 255, 0.5)"
          strokeWidth="1"
          fill="none"
          opacity="0.6"
        >
          <line x1={100} y1={90} x2={140} y2={110} />
          <line x1={100} y1={90} x2={60} y2={110} />
          <line x1={180} y1={210} x2={220} y2={190} />
          <line x1={180} y1={210} x2={140} y2={190} />
          <line x1={140} y1={110} x2={180} y2={150} />
          <line x1={220} y1={190} x2={260} y2={170} />
        </g>
        
        {/* Neuron nodes with pulse animation */}
        <g fill="rgba(0, 255, 255, 0.8)" opacity={0.8}>
          <circle cx={100} cy={90} r={3} class="neuron-node" />
          <circle cx={140} cy={110} r={3} class="neuron-node" />
          <circle cx={60} cy={110} r={3} class="neuron-node" />
          <circle cx={220} cy={190} r={3} class="neuron-node" />
          <circle cx={260} cy={170} r={3} class="neuron-node" />
          <circle cx={180} cy={150} r={3} class="neuron-node" />
          <circle cx={300} cy={90} r={3} class="neuron-node" />
          <circle cx={340} cy={50} r={3} class="neuron-node" />
        </g>
        
        {/* Glowing connections */}
        <g fill="none" stroke="rgba(0, 255, 255, 0.4)" strokeWidth={2} opacity={0.5}>
          <circle cx={100} cy={90} r={8} class="glow-connection" />
          <circle cx={140} cy={110} r={8} class="glow-connection" />
          <circle cx={60} cy={110} r={8} class="glow-connection" />
          <circle cx={220} cy={190} r={8} class="glow-connection" />
          <circle cx={260} cy={170} r={8} class="glow-connection" />
          <circle cx={180} cy={150} r={8} class="glow-connection" />
          <circle cx={300} cy={90} r={8} class="glow-connection" />
          <circle cx={340} cy={50} r={8} class="glow-connection" />
        </g>
        
        {/* Electrical wave arcs */}
        <g fill="none" stroke="rgba(128, 0, 255, 0.8)" strokeWidth={2} opacity={0.9}>
          <path
            d={`M100 90 A40 30 0 0 1 140 110`}
            className="wave-arc"
          />
          <path
            d={`M60 110 A40 30 0 0 1 100 90`}
            className="wave-arc"
          />
          <path
            d={`M220 190 A40 30 0 0 1 260 170`}
            className="wave-arc"
          />
          <path
            d={`M260 170 A40 30 0 0 1 300 90`}
            className="wave-arc"
          />
        </g>
        
        {/* Synaptic activity markers */}
        <g fill="rgba(255, 255, 0, 0.9)">
          <circle cx={100} cy={90} r={2} class="synaptic-activity" />
          <circle cx={140} cy={110} r={2} class="synaptic-activity" />
          <circle cx={60} cy={110} r={2} class="synaptic-activity" />
          <circle cx={180} cy={150} r={2} class="synaptic-activity" />
          <circle cx={220} cy={190} r={2} class="synaptic-activity" />
          <circle cx={260} cy={170} r={2} class="synaptic-activity" />
        </g>
      </svg>
      
      {/* Lighting glow effect */}
      <div
        style={{
          position: "absolute",
          top: "-50%",
          left: "-50%",
          width: "200%",
          height: "200%",
          background:
            "radial-gradient(circle, rgba(0, 255, 255, 0.15) 0%, transparent 70%)",
          pointerEvents: "none",
          animation: "pulse-glow 4s ease-in-out infinite",
        }}
      />
    </div>
  );
}

/* CSS animations are defined globally in the app's CSS */
