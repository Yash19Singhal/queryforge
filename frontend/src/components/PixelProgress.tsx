"use client";

import React from "react";

interface PixelProgressProps {
  value: number; // 0-100
  maxSegments?: number;
  colorClass?: string;
}

export default function PixelProgress({
  value,
  maxSegments = 20,
  colorClass = "green",
}: PixelProgressProps) {
  const filledCount = Math.round((value / 100) * maxSegments);

  return (
    <div className={`pixel-progress pixel-progress--${colorClass}`}>
      {Array.from({ length: maxSegments }).map((_, i) => (
        <div
          key={i}
          className={`pixel-progress-segment ${i < filledCount ? "filled" : "empty"}`}
        />
      ))}
    </div>
  );
}
