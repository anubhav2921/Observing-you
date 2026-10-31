# AI Study Focus Monitor

A real-time, multi-modal computer vision and temporal behavior recognition system designed to monitor study engagement, posture integrity, and fatigue markers without generating false alarms during legitimate study activities (such as looking down while typing, taking notes, reading textbooks, or quiet contemplation).

---

## 1. System Architecture & Directory Structure

The repository follows a clean, decoupled, enterprise-grade architecture:

```
modal-object/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/          # REST endpoints (/api/health, /api/config, /api/session/reset)
│   │   │   └── websocket/       # Real-time WebSocket streaming (/ws/monitor)
│   │   ├── core/                # Configuration & structured logging
│   │   ├── schemas/             # Pydantic v2 data models & event schemas
│   │   ├── models/              # Model loaders & asset verification
│   │   ├── services/
│   │   │   ├── detection/       # UpperBodyDetector, YOLOService, FocusMonitor
│   │   │   ├── behavior/        # BehaviorLabel & Observation dataclasses
│   │   │   ├── decision/        # StateMachine, TemporalDecisionEngine
│   │   │   ├── audio/           # CentralAudioManager with priority preemption
│   │   │   ├── session/         # Multi-client SessionManager
│   │   │   ├── recommendation/  # Non-shaming coaching guidance engine
│   │   │   └── analytics/       # JSONL audit logger
│   │   ├── pipelines/           # Per-session frame processing & rationale builder
│   │   ├── utils/               # Geometry, IoU, 2D distance helpers
│   │   └── main.py              # FastAPI entrypoint & static asset server
│   ├── tests/                   # Unit, integration, and WebSocket test suites
│   ├── requirements.txt         # Python dependencies
│   └── pyproject.toml           # Build configuration
│
├── frontend/
│   ├── public/                  # Static assets & icons
│   ├── src/
│   │   ├── components/          # Modular UI components
│   │   ├── pages/               # Dashboard views
│   │   ├── services/            # Flow-controlled WebSocket client
│   │   ├── hooks/               # State lifecycle hooks
│   │   ├── styles/              # Accessible CSS dashboard styles
│   │   ├── utils/               # WebRTC CameraManager, BrowserAudioController
│   │   ├── assets/              # Frontend images & icons
│   │   ├── App.js               # Main application coordinator
│   │   └── main.js              # Vite application entrypoint
│   ├── index.html               # Single-page application HTML
│   ├── package.json             # NPM scripts & dependencies
│   └── vite.config.js           # Vite development server & reverse proxy
│
├── assets/
│   ├── audio/                   # Audio alert files (.mp3)
│   ├── models/                  # YOLOv8 weights (.pt) & MediaPipe task bundles (.task)
│   └── icons/                   # Favicon & UI icons
│
├── infrastructure/
│   ├── docker/                  # Dockerfile.backend & Dockerfile.frontend
│   ├── deployment/              # supervisord.conf & nginx.conf
│   └── scripts/                 # start_all.ps1 & start_all.sh
│
├── docs/                        # Persistent project memory (9 core specifications)
│   ├── PID.md                   # Project Identity Document
│   ├── ARCHITECTURE.md          # End-to-end system architecture
│   ├── DESIGN.md                # Algorithmic decisions & trade-offs
│   ├── RULES.md                 # Invariant engineering rules
│   ├── PHASES.md                # 10 development milestones
│   ├── API.md                   # REST contracts & WebSocket schemas
│   ├── FILE_MAP.md              # File & symbol registry
│   ├── CHANGELOG.md             # Chronological audit log
│   └── CURRENT_STATUS.md        # Live subsystem health
│
├── shared/
│   └── contracts/               # Cross-language JSON schemas
│
├── AGENTS.md                    # AI agent instructions & persistent memory entrypoint
├── README.md                    # Project overview & quickstart
├── .env.example                 # Example environment variables
├── .gitignore                   # Version control exclusions
└── docker-compose.yml           # Multi-container deployment
```

---

## 2. Quickstart & Execution Modes

### Mode A: Local Machine OpenCV Native Mode
Runs the computer vision engine locally using OpenCV video capture and native Pygame audio alerts:
```bash
python run_app.py --mode local
```

### Mode B: Web Dashboard Mode (FastAPI + Embedded Assets)
Starts the FastAPI server hosting REST APIs, the `/ws/monitor` WebSocket, and serving the pre-built web dashboard:
```bash
python run_app.py --mode web --port 8000
```
Open your browser at `http://127.0.0.1:8000/`.

### Development Mode (FastAPI Backend + Vite Hot Reload)
Concurrently runs the FastAPI backend on port 8000 and the Vite frontend dev server on port 5173 with automatic reverse-proxying:
```bash
python run_app.py --mode dev
```
Open your browser at `http://127.0.0.1:5173/`.

---

## 3. Running Test Suites

Run all unit, integration, and WebSocket tests:
```bash
python -m unittest discover -s backend/tests
```

Or run targeted test suites:
```bash
python -m unittest backend/tests/integration/test_critical_fixes.py
python -m unittest backend/tests/unit/test_state_machine.py
python -m unittest backend/tests/unit/test_upper_body_detector.py
python -m unittest backend/tests/websocket/test_websocket_stream.py
```

---

## 4. Persistent Project Documentation

All agents and contributors must adhere to `AGENTS.md` and consult `/docs`:
- Architectural pipelines: [`docs/ARCHITECTURE.md`](file:///c:/Users/vinu/modal-object/docs/ARCHITECTURE.md)
- Trade-offs & algorithm parameters: [`docs/DESIGN.md`](file:///c:/Users/vinu/modal-object/docs/DESIGN.md)
- REST & WebSocket schemas: [`docs/API.md`](file:///c:/Users/vinu/modal-object/docs/API.md)
- Coding constraints: [`docs/RULES.md`](file:///c:/Users/vinu/modal-object/docs/RULES.md)

