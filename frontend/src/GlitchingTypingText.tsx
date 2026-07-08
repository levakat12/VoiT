import { useEffect, useMemo, useState } from "react";
import "./GlitchingTypingText.css";

const DEFAULT_GLITCH_CHARS =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789#$%&@!?<>[]{}+-=*/\\|_";

type GlitchingTypingTextProps = {
  text: string;
  className?: string;
  displayCaret?: boolean;
  typingDuration?: number;
  glitchProbability?: number;
  potentialGlitchInterval?: number;
  nextCharProbability?: number;
  startDelay?: number;
};

export default function GlitchingTypingText({
  text,
  className = "",
  displayCaret = true,
  typingDuration = 2600,
  glitchProbability = 0.2,
  potentialGlitchInterval = 120,
  nextCharProbability = 0.9,
  startDelay = 0,
}: GlitchingTypingTextProps) {
  const safeText = text || "";
  const [sliceIndex, setSliceIndex] = useState(0);
  const [renderedText, setRenderedText] = useState(safeText);
  const typingInterval = useMemo(
    () => Math.max(12, Math.floor(typingDuration / Math.max(safeText.length, 1))),
    [safeText.length, typingDuration],
  );

  useEffect(() => {
    setSliceIndex(0);
    setRenderedText(safeText);

    let glitchIntervalId: number | undefined;
    let typingIntervalId: number | undefined;
    const delayTimeoutId = window.setTimeout(() => {
      glitchIntervalId = window.setInterval(() => {
        setRenderedText((currentText) => {
          if (Math.random() <= glitchProbability) {
            return randomizeTextCharacter(safeText);
          }
          return currentText !== safeText ? safeText : currentText;
        });
      }, potentialGlitchInterval);

      typingIntervalId = window.setInterval(() => {
        setSliceIndex((currentIndex) => {
          if (currentIndex >= safeText.length) {
            window.clearInterval(typingIntervalId);
            return currentIndex;
          }

          const shouldAdvance = Math.random() <= nextCharProbability || currentIndex === 0;
          return shouldAdvance ? currentIndex + 1 : currentIndex;
        });
      }, typingInterval);
    }, startDelay);

    return () => {
      window.clearTimeout(delayTimeoutId);
      window.clearInterval(glitchIntervalId);
      window.clearInterval(typingIntervalId);
    };
  }, [
    glitchProbability,
    nextCharProbability,
    potentialGlitchInterval,
    safeText,
    startDelay,
    typingInterval,
  ]);

  return (
    <p className={`glitchingText ${displayCaret ? "withCaret" : ""} ${className}`} aria-label={safeText}>
      {renderedText.slice(0, sliceIndex)}
    </p>
  );
}

function randomizeTextCharacter(text: string): string {
  if (!text.length) return text;

  const charToReplaceIndex = Math.floor(Math.random() * text.length);
  const randomChar = DEFAULT_GLITCH_CHARS.charAt(Math.floor(Math.random() * DEFAULT_GLITCH_CHARS.length));
  const splitText = text.split("");
  splitText[charToReplaceIndex] = randomChar;
  return splitText.join("");
}
