/**
 * frontend/src/main.js — Vite Frontend Entrypoint.
 * Loads stylesheets, initializes landing page routing, and instantiates StudyMonitorApp.
 */
import "./styles/dashboard.css";
import "./styles/landing.css";
import { StudyMonitorApp } from "./App.js";
import { initLandingPage } from "./landing.js";

document.addEventListener("DOMContentLoaded", () => {
  initLandingPage();
  if (!window.studyMonitorApp) {
    window.studyMonitorApp = new StudyMonitorApp();
  }
});
