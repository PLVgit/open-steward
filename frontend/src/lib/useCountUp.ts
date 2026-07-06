import { useEffect, useState } from "react";

/** Animate a number from 0 to `value` on first render (~600ms, ease-out).
 *  Snaps instantly when reduced motion is preferred or matchMedia is
 *  unavailable (e.g. jsdom) — so tests and accessibility both see the final
 *  value immediately. */
export function useCountUp(value: number, durationMs = 600): number {
  const animatable =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const [display, setDisplay] = useState(animatable ? 0 : value);

  useEffect(() => {
    if (!animatable) {
      setDisplay(value);
      return;
    }
    let frame: number;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / durationMs, 1);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setDisplay(Math.round(eased * value));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, durationMs]);

  return display;
}
