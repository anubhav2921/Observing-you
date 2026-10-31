/**
 * frontend/src/landing.js — Client controller for Futuristic SaaS Landing Page
 * Coordinates:
 *   1. Cinematic Zoom-In Intro Animation with smooth camera expansion into landing page.
 *   2. View routing between Landing Page and Monitoring Dashboard.
 *   3. Smooth anchor transitions, scroll glassmorphism, and replay functionality.
 */

export function initLandingPage() {
  const landingView = document.getElementById("landing-view");
  const dashboardView = document.getElementById("dashboard-view");
  const landingHeader = document.querySelector(".landing-header");
  const landingHero = document.getElementById("landing-hero");
  const introOverlay = document.getElementById("cinematic-intro");
  const introSkipBtn = document.getElementById("intro-skip-btn");
  const replayIntroBtn = document.getElementById("replay-intro-btn");

  if (!landingView || !dashboardView) {
    return;
  }

  // Session state tracker: intro plays once per page load, never on internal navigation
  let hasPlayedIntroThisSession = false;
  let introExitTimer = null;
  let introCleanupTimer = null;

  // =========================================================================
  // 1. CINEMATIC INTRO ANIMATION CONTROLLER
  // =========================================================================
  function playCinematicIntro(forceReplay = false) {
    if (!introOverlay) return;

    // Do not play if starting directly at dashboard
    const hash = window.location.hash.toLowerCase();
    if (!forceReplay && (hash === "#monitor" || hash === "#dashboard")) {
      introOverlay.classList.add("intro-hidden");
      return;
    }

    // Do not replay automatically on internal route switching back to #
    if (!forceReplay && hasPlayedIntroThisSession) {
      introOverlay.classList.add("intro-hidden");
      return;
    }

    // Clear any pending timers
    if (introExitTimer) clearTimeout(introExitTimer);
    if (introCleanupTimer) clearTimeout(introCleanupTimer);

    hasPlayedIntroThisSession = true;

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion && !forceReplay) {
      introOverlay.classList.add("intro-hidden");
      landingHero?.classList.add("hero-cinematic-enter");
      return;
    }

    // Prepare elements
    introOverlay.classList.remove("intro-hidden", "intro-exiting");
    landingHero?.classList.remove("hero-cinematic-enter");

    // Force animation restart on replay
    if (forceReplay) {
      const centerStage = introOverlay.querySelector(".intro-center-stage");
      if (centerStage) {
        centerStage.style.animation = "none";
        // Force reflow
        void centerStage.offsetWidth;
        centerStage.style.animation = "";
      }
      const logoBox = introOverlay.querySelector(".intro-logo-box");
      if (logoBox) {
        logoBox.style.animation = "none";
        void logoBox.offsetWidth;
        logoBox.style.animation = "";
      }
      const textLockup = introOverlay.querySelector(".intro-text-lockup");
      if (textLockup) {
        textLockup.style.animation = "none";
        void textLockup.offsetWidth;
        textLockup.style.animation = "";
      }
    }

    // Step A: At 2.7s, trigger cinematic zoom toward camera and radial bloom
    introExitTimer = setTimeout(() => {
      introOverlay.classList.add("intro-exiting");
      // Animate the hero reveal in sync with the light sweep
      landingHero?.classList.add("hero-cinematic-enter");
    }, 2700);

    // Step B: At 3.5s, completely hide intro overlay
    introCleanupTimer = setTimeout(() => {
      introOverlay.classList.add("intro-hidden");
      introOverlay.classList.remove("intro-exiting");
    }, 3550);
  }

  function skipCinematicIntro() {
    if (!introOverlay) return;
    if (introExitTimer) clearTimeout(introExitTimer);
    if (introCleanupTimer) clearTimeout(introCleanupTimer);

    introOverlay.classList.add("intro-exiting");
    landingHero?.classList.add("hero-cinematic-enter");

    setTimeout(() => {
      introOverlay.classList.add("intro-hidden");
      introOverlay.classList.remove("intro-exiting");
    }, 250);
  }

  // Bind Skip & Replay buttons
  introSkipBtn?.addEventListener("click", skipCinematicIntro);

  replayIntroBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    window.scrollTo({ top: 0, behavior: "smooth" });
    playCinematicIntro(true);
  });

  // Start intro animation on initial page load
  playCinematicIntro(false);

  // =========================================================================
  // 2. VIEW ROUTING & STATE SYNCHRONIZATION
  // =========================================================================
  function updateViewFromHash() {
    const hash = window.location.hash.toLowerCase();
    const isDashboard = hash === "#monitor" || hash === "#dashboard";

    if (isDashboard) {
      // If user enters dashboard, always hide intro instantly
      introOverlay?.classList.add("intro-hidden");
      landingView.style.display = "none";
      dashboardView.style.display = "block";
      document.body.classList.remove("landing-view-active");
      window.scrollTo({ top: 0, behavior: "instant" });
    } else {
      landingView.style.display = "block";
      dashboardView.style.display = "none";
      document.body.classList.add("landing-view-active");
    }
  }

  window.addEventListener("hashchange", updateViewFromHash);
  // Initial route check
  updateViewFromHash();

  // =========================================================================
  // 3. LAUNCH MONITOR & START MONITORING ACTION LISTENERS
  // =========================================================================
  document.querySelectorAll(".action-launch-monitor").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      window.location.hash = "#monitor";
    });
  });

  document.querySelectorAll(".action-start-monitoring").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      window.location.hash = "#monitor";
      // Auto-trigger camera start if session isn't running
      setTimeout(() => {
        const startBtn = document.getElementById("start-btn");
        if (startBtn && !startBtn.disabled) {
          startBtn.click();
        }
      }, 400);
    });
  });

  // =========================================================================
  // 4. SMOOTH NAVIGATION FOR IN-PAGE ANCHORS (#features, #how-it-works, etc.)
  // =========================================================================
  document.querySelectorAll('.landing-nav-link, a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      const targetId = this.getAttribute("href");
      if (targetId && targetId.startsWith("#") && targetId.length > 1) {
        if (targetId === "#monitor" || targetId === "#dashboard" || targetId === "#replay") {
          return;
        }
        const targetElement = document.querySelector(targetId);
        if (targetElement) {
          e.preventDefault();
          targetElement.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        }
      }
    });
  });

  // =========================================================================
  // 5. HEADER GLASSMORPHISM ON SCROLL
  // =========================================================================
  window.addEventListener("scroll", () => {
    if (window.scrollY > 40) {
      landingHeader?.classList.add("scrolled");
    } else {
      landingHeader?.classList.remove("scrolled");
    }
  });
}
