# NeuroLIMS

An interactive neuroscience learning platform. NeuroLIMS combines a clickable brain atlas,
live literature search, and a neuron simulator in one web app, so you can explore a
brain region, read the most-cited research on it, and model how neurons behave.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **Brain Atlas.** An interactive SVG map with external (lateral) and internal (midsagittal)
  views. Hover over a region to see its name, or click it to open a panel describing its function.
- **Research explorer.** Pulls papers for the selected region from the
  [OpenAlex](https://openalex.org/) API, either ranked by citation count or sorted by
  newest. You can filter by publication year and save references to come back to later.
- **Neuron simulation.** A leaky integrate-and-fire (LIF) model that runs on the backend.
  You set the membrane time constant, spike threshold, stimulus (constant or pulsed), and
  GABA/glutamate levels, then see the membrane-voltage trace, the spike times, and summary
  metrics (spike count, firing rate, mean and peak V<sub>m</sub>).
- **Saved experiments.** Simulation parameters and results are stored per user in SQLite.
- **AI assistant.** A chat widget backed by the Anthropic Claude API. It asks for your
  expertise level (from undergraduate to clinician) and adjusts the depth of its answers to match.
- **User accounts.** Registration and sign-in, plus a seeded demo account.

## Tech stack

| Layer    | Technology |
| -------- | ---------- |
| Frontend | React 18 (single-page app, loaded from a CDN), custom CSS design system |
| Backend  | FastAPI, Pydantic, SQLAlchemy, httpx |
| Database | SQLite |
| External | OpenAlex API (literature), Anthropic API (chat assistant) |

## Architecture

```
┌──────────────────────┐   HTTP/JSON   ┌───────────────────────────┐
│  frontend/index.html │ ────────────▶ │  backend/app.py (FastAPI) │
│  React SPA           │               │  ├─ /auth/*   accounts    │
└──────────────────────┘               │  ├─ /simulate LIF model   │
                                       │  ├─ /experiments          │
                                       │  ├─ /research/*  ──────────────▶ OpenAlex
                                       │  └─ /api/chat    ──────────────▶ Anthropic
                                       └─────────────┬─────────────┘
                                                     │ SQLAlchemy
                                               neurolims.db (SQLite)
```

## Getting started

### Prerequisites

- Python 3.10+
- A modern web browser
- *(Optional)* An [Anthropic API key](https://console.anthropic.com/) for the AI assistant

### 1. Run the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
ANTHROPIC_API_KEY=your-key-here      # optional, enables the chat assistant
OPENALEX_MAILTO=you@example.com      # optional, identifies you to OpenAlex
```

Start the server:

```bash
uvicorn app:app --reload
```

The API runs at <http://127.0.0.1:8000>, and FastAPI serves interactive docs at
<http://127.0.0.1:8000/docs>.

### 2. Run the frontend

The frontend has no build step. Serve the `frontend/` directory:

```bash
cd frontend
python -m http.server 5500
```

Then open <http://localhost:5500>. Sign in with the demo account
(`demo@neurolims.edu` / `demo1234`), or create a new one.

## API overview

| Method | Endpoint             | Description |
| ------ | -------------------- | ----------- |
| `POST` | `/auth/register`     | Create an account |
| `POST` | `/auth/login`        | Sign in |
| `POST` | `/simulate`          | Run a LIF simulation; returns the voltage trace, spike times and metrics |
| `GET`  | `/experiments`       | List a user's saved experiments |
| `POST` | `/experiments`       | Save an experiment |
| `GET`  | `/research/papers`   | Most-cited papers for a brain region (OpenAlex) |
| `GET`  | `/research/studies`  | Most recent studies matching a search term (OpenAlex) |
| `POST` | `/api/chat`          | Send a message to the AI assistant |
| `GET`  | `/health`            | Health check |

## The simulation model

Each time step updates the membrane potential with the leaky integrate-and-fire equation:

```
τ · dV/dt = (V_rest − V) + R · I(t)
```

When V crosses the threshold, the simulator records a spike and resets V to `V_reset`.
Neuromodulators are modelled in a simplified way: GABA (inhibitory) raises the effective
threshold and scales down the input current, while glutamate (excitatory) does the reverse.

Defaults: V<sub>rest</sub> = −70 mV, V<sub>reset</sub> = −75 mV, R = 10 MΩ, dt = 0.1 ms.

## Project structure

```
NeuroLIMS/
├── backend/
│   ├── app.py              # FastAPI app: routes, LIF simulator, OpenAlex and Anthropic clients
│   ├── database.py         # SQLAlchemy models (User, Experiment) and DB setup
│   └── requirements.txt
├── frontend/
│   ├── index.html          # The full React app (runs directly in the browser)
│   ├── App.jsx             # The same app as an ES module, for use with a bundler
│   └── *.PNG               # Brain atlas reference images
└── LICENSE
```

## Roadmap

- Hash passwords (e.g. bcrypt) and add token-based sessions
- Move the API base URL into configuration
- Persist saved references to the database
- Add tests for the simulation model and the API

## License

[MIT](LICENSE)
