import type { CSSProperties } from "react";
import "./ASCIIText.css";

type ASCIITextProps = {
  text?: string;
};

export default function ASCIIText({ text = "VoiT" }: ASCIITextProps) {
  return (
    <span className="wordLogo" aria-hidden="true">
      {Array.from(text).map((letter, index) => (
        <span
          className="wordLogoLetter"
          key={`${letter}-${index}`}
          style={{ "--letter-index": index } as CSSProperties}
        >
          {letter}
        </span>
      ))}
    </span>
  );
}
