"""
run_app.py — Unified Root CLI Entrypoint for AI Study Monitoring System.
Supports:
    Mode A: Local Machine Mode (OpenCV + Local Audio + Local HUD)
    Mode B: Web Dashboard Mode (FastAPI + WebSockets + Web Dashboard)
    Dev Mode: Backend + Vite Frontend concurrent startup
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser


def run_local_mode() -> None:
    """Run Mode A: Local Machine OpenCV Webcam Monitor."""
    print("=" * 65)
    print("  Starting Mode A: Local Machine OpenCV Study Monitor")
    print("=" * 65)
    try:
        from backend.scripts import run_webcam
        run_webcam.main()
    except KeyboardInterrupt:
        print("\n[Local Mode] Exited via keyboard interrupt.")
    except Exception as e:
        print(f"\n[Local Mode] Error running local engine: {e}")
        sys.exit(1)


def run_web_mode(host: str = "127.0.0.1", port: int = 8000, reload: bool = False, open_browser: bool = True) -> None:
    """Run Mode B: Web Dashboard Server (FastAPI + WebSockets)."""
    print("=" * 65)
    print("  Starting Mode B: Web Dashboard Monitor")
    print(f"  Access Dashboard at: http://{host}:{port}/")
    print("=" * 65)

    if open_browser:
        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(f"http://{host}:{port}/")
            except Exception:
                pass
        import threading
        threading.Thread(target=_open, daemon=True).start()

    try:
        import uvicorn
        uvicorn.run("backend.app.main:app", host=host, port=port, reload=reload, log_level="info")
    except KeyboardInterrupt:
        print("\n[Web Mode] Server stopped cleanly.")
    except Exception as e:
        print(f"\n[Web Mode] Server error: {e}")
        sys.exit(1)


def run_dev_mode(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run Dev Mode: FastAPI Backend + Vite Frontend concurrently."""
    print("=" * 65)
    print("  Starting Dev Mode: FastAPI Backend + Vite Frontend")
    print(f"  Backend:  http://{host}:{port}")
    print(f"  Frontend: http://{host}:5173")
    print("=" * 65)

    python_exe = sys.executable
    backend_cmd = [python_exe, "-m", "uvicorn", "backend.app.main:app", "--host", host, "--port", str(port), "--reload"]
    frontend_cmd = ["npm", "--prefix", "frontend", "run", "dev"]

    backend_proc = None
    frontend_proc = None

    try:
        print("[Dev] Spawning backend process...")
        backend_proc = subprocess.Popen(backend_cmd)

        print("[Dev] Spawning frontend process...")
        frontend_proc = subprocess.Popen(frontend_cmd, shell=True)

        print("\n[Dev] Both servers running. Press Ctrl+C to terminate both.\n")
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("[Dev] Backend process exited.")
                break
            if frontend_proc.poll() is not None:
                print("[Dev] Frontend process exited.")
                break

    except KeyboardInterrupt:
        print("\n[Dev] Shutting down development servers...")
    finally:
        if backend_proc and backend_proc.poll() is None:
            backend_proc.terminate()
        if frontend_proc and frontend_proc.poll() is None:
            frontend_proc.terminate()
        print("[Dev] All servers terminated.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Study Focus Monitor — Dual-Mode Execution Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_app.py --mode local
  python run_app.py --mode web
  python run_app.py --mode dev
  python run_app.py --mode web --port 8080 --no-browser
        """,
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["local", "web", "dev"],
        default="web",
        help="Execution mode: 'local' (OpenCV mode), 'web' (Web dashboard mode), 'dev' (FastAPI + Vite)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host address for web server (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for web server (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes (web mode)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser in web mode")
    parser.add_argument("--diagnostic", "--diag", action="store_true", help="Run in Safe Diagnostic Mode (detection active, audio muted)")

    args = parser.parse_args()

    if args.diagnostic:
        import backend.app.core.config as cfg
        cfg.DIAGNOSTIC_MODE = True
        print("[Diagnostic Mode] Safe Diagnostic Mode enabled: All detectors active, audio alerts suppressed.")

    if args.mode == "local":
        run_local_mode()
    elif args.mode == "web":
        run_web_mode(host=args.host, port=args.port, reload=args.reload, open_browser=not args.no_browser)
    elif args.mode == "dev":
        run_dev_mode(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
