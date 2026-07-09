import { CSSProperties, useEffect, useRef, useState } from "react";
import voitLogoUrl from "./assets/voit-logo-clean.png";
import "./StaggeredMenu.css";

type MenuItem = {
  label: string;
  ariaLabel: string;
  link: string;
};

type SocialItem = {
  label: string;
  link: string;
};

type StaggeredMenuProps = {
  items: MenuItem[];
  socialItems?: SocialItem[];
  position?: "left" | "right";
  displaySocials?: boolean;
  displayItemNumbering?: boolean;
  colors?: string[];
  accentColor?: string;
  className?: string;
};

type MenuStyle = CSSProperties & {
  "--sm-accent"?: string;
  "--sm-color-one"?: string;
  "--sm-color-two"?: string;
  "--sm-color-three"?: string;
  "--sm-index"?: number;
};

export default function StaggeredMenu({
  items,
  socialItems = [],
  position = "right",
  displaySocials = true,
  displayItemNumbering = true,
  colors = ["#ff4800", "#e300ff", "#00fff3"],
  accentColor = "#f4f4f4",
  className = "",
}: StaggeredMenuProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);

  function clearCloseTimer() {
    if (closeTimerRef.current == null) return;
    window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  }

  function openMenu() {
    clearCloseTimer();
    setOpen(true);
  }

  function closeMenu() {
    clearCloseTimer();
    setOpen(false);
  }

  function scheduleClose() {
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setOpen(false);
      closeTimerRef.current = null;
    }, 280);
  }

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        closeMenu();
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeMenu();
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  useEffect(() => {
    return () => clearCloseTimer();
  }, []);

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      const isRightHotEdge = position === "right" && event.clientX >= window.innerWidth - 32;
      const isLeftHotEdge = position === "left" && event.clientX <= 32;

      if (isRightHotEdge || isLeftHotEdge) {
        openMenu();
      }
    }

    window.addEventListener("pointermove", handlePointerMove);
    return () => window.removeEventListener("pointermove", handlePointerMove);
  }, [position]);

  const style: MenuStyle = {
    "--sm-accent": accentColor,
    "--sm-color-one": colors[0] ?? "#ff4800",
    "--sm-color-two": colors[1] ?? "#e300ff",
    "--sm-color-three": colors[2] ?? "#00fff3",
  };

  return (
    <div
      ref={wrapperRef}
      className={`staggered-menu-wrapper ${className}`}
      data-position={position}
      data-open={open || undefined}
      style={style}
    >
      <div className="staggered-menu-header" aria-label="Main navigation">
        <span className="sm-brand">
          <img className="sm-brand-glow" src={voitLogoUrl} alt="" aria-hidden="true" draggable={false} />
          <img className="sm-brand-logo" src={voitLogoUrl} alt="VoiT" draggable={false} />
        </span>
      </div>

      <button
        className="sm-hot-corner"
        aria-label="Open navigation tray"
        aria-expanded={open}
        aria-controls="staggered-menu-panel"
        onPointerEnter={openMenu}
        onFocus={openMenu}
        onClick={openMenu}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openMenu();
          }
        }}
        type="button"
      />

      <div className="sm-prelayers" aria-hidden="true">
        <div className="sm-prelayer sm-prelayer-one" />
        <div className="sm-prelayer sm-prelayer-two" />
      </div>

      <aside
        id="staggered-menu-panel"
        className="staggered-menu-panel"
        aria-hidden={!open}
        onPointerEnter={openMenu}
        onPointerLeave={scheduleClose}
      >
        <div className="sm-panel-glow" aria-hidden="true" />
        <div className="sm-panel-inner">
          <nav aria-label="Main menu">
            <ul className="sm-panel-list" role="list" data-numbering={displayItemNumbering || undefined}>
              {items.map((item, index) => (
                <li className="sm-panel-itemWrap" key={item.label} style={{ "--sm-index": index } as MenuStyle}>
                  <a
                    className="sm-panel-item"
                    href={item.link}
                    aria-label={item.ariaLabel}
                    data-index={index + 1}
                    onClick={() => setOpen(false)}
                  >
                    <span className="sm-panel-itemLabel">{item.label}</span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          {displaySocials && socialItems.length > 0 ? (
            <div className="sm-socials" aria-label="Project links">
              <h3 className="sm-socials-title">Project</h3>
              <ul className="sm-socials-list" role="list">
                {socialItems.map((item, index) => (
                  <li key={item.label} className="sm-socials-item" style={{ "--sm-index": index } as MenuStyle}>
                    <a href={item.link} target="_blank" rel="noopener noreferrer" className="sm-socials-link">
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
