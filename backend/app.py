from fastapi import FastAPI, Query, HTTPException, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, init_db, User, Experiment
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv
import os
load_dotenv()


app = FastAPI(title="NeuroLIMS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENALEX_BASE = "https://api.openalex.org/works"
MAILTO = os.getenv("OPENALEX_MAILTO", "neurolims@demo.edu")
init_db()


def seed_demo_user():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "demo@neurolims.edu").first()
        if not existing:
            demo = User(
                name="Guest",
                email="demo@neurolims.edu",
                password="demo1234",
            )
            db.add(demo)
            db.commit()
    finally:
        db.close()


seed_demo_user()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
class StimulusInput(BaseModel):
    type: str
    amplitude: float
    pulseWidth: float
    pulseFreq: float

class NeuroInput(BaseModel):
    gaba: float
    glu: float

class SimulationMetrics(BaseModel):
    totalSpikes: int
    firingRateHz: float
    meanVm: float
    peakVm: float    
           
class SaveExperimentRequest(BaseModel):
    name: str
    user_email: str
    tau: float
    Vth: float
    tSim: float
    stim: StimulusInput
    neuro: NeuroInput
    metrics: SimulationMetrics
    
    
class AuthRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class UserResponse(BaseModel):
    name: str
    email: str


class StimulusInput(BaseModel):
    type: str = Field(default="constant", pattern="^(constant|pulse)$")
    amplitude: float = 3.0
    pulseWidth: float = 10.0
    pulseFreq: float = 20.0


class NeuroInput(BaseModel):
    gaba: float = 0.0
    glu: float = 0.0


class SimulationInput(BaseModel):
    tau: float = 20.0
    Vth: float = -55.0
    tSim: float = 200.0
    stim: StimulusInput
    neuro: NeuroInput


class SimulationMetrics(BaseModel):
    totalSpikes: int
    firingRateHz: float
    meanVm: float
    peakVm: float


class SimulationResult(BaseModel):
    times: List[float]
    voltage: List[float]
    spikeTimes: List[float]
    metrics: SimulationMetrics


USERS: List[Dict[str, str]] = [
    {"name": "Guest", "email": "demo@neurolims.edu", "password": "demo1234"}
]


def lif_simulation(payload: SimulationInput) -> Dict[str, Any]:
    Vrest = -70.0
    Vreset = -75.0
    R = 10.0
    dt = 0.1

    tau = float(payload.tau)
    Vth = float(payload.Vth)
    t_sim = float(payload.tSim)

    gaba = max(0.0, min(1.0, payload.neuro.gaba))
    glu = max(0.0, min(1.0, payload.neuro.glu))

    threshold_shift = (gaba * 5.0) + (glu * -5.0)
    current_scale = (1.0 - 0.4 * gaba) * (1.0 + 0.4 * glu)
    effective_vth = Vth + threshold_shift

    steps = max(1, int(t_sim / dt))
    times: List[float] = []
    voltage: List[float] = []
    spike_times: List[float] = []

    vm = Vrest

    for i in range(steps):
        t = i * dt

        if payload.stim.type == "constant":
            current = payload.stim.amplitude
        else:
            period_ms = 1000.0 / max(payload.stim.pulseFreq, 1e-6)
            phase = t % period_ms
            current = payload.stim.amplitude if phase < payload.stim.pulseWidth else 0.0

        current *= current_scale

        dvm = ((Vrest - vm) + (R * current)) / tau * dt
        vm += dvm

        if vm >= effective_vth:
            spike_times.append(round(t, 4))
            vm = Vreset

        times.append(round(t, 4))
        voltage.append(round(vm, 4))

    total_spikes = len(spike_times)
    firing_rate_hz = total_spikes / (t_sim / 1000.0) if t_sim > 0 else 0.0
    mean_vm = sum(voltage) / len(voltage)
    peak_vm = max(voltage) if voltage else Vrest

    return {
        "times": times,
        "voltage": voltage,
        "spikeTimes": spike_times,
        "metrics": {
            "totalSpikes": total_spikes,
            "firingRateHz": round(firing_rate_hz, 3),
            "meanVm": round(mean_vm, 3),
            "peakVm": round(peak_vm, 3),
        },
    }


async def openalex_search(search: str, page: int, per_page: int, sort: str, filters: Optional[str] = None) -> Dict[str, Any]:
    params = {
        "search": search,
        "page": page,
        "per_page": per_page,
        "sort": sort,
        "mailto": MAILTO,
    }
    if filters:
        params["filter"] = filters

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(OPENALEX_BASE, params=params)
        response.raise_for_status()
        return response.json()


@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "NeuroLIMS backend is running"}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=UserResponse)
def login(payload: AuthRequest, db: Session = Depends(get_db)) -> Dict[str, str]:
    user = (
        db.query(User)
        .filter(User.email == payload.email.lower(), User.password == payload.password)
        .first()
    )

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"name": user.name, "email": user.email}


@app.post("/auth/register", response_model=UserResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> Dict[str, str]:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=payload.name,
        email=payload.email.lower(),
        password=payload.password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"name": new_user.name, "email": new_user.email}


@app.post("/simulate", response_model=SimulationResult)
def simulate(payload: SimulationInput) -> Dict[str, Any]:
    return lif_simulation(payload)

@app.get("/experiments")
def get_experiments(user_email: str, db: Session = Depends(get_db)):
    experiments = (
        db.query(Experiment)
        .filter(Experiment.user_email == user_email.lower())
        .order_by(Experiment.id.desc())
        .all()
    )

    return [
        {
            "id": e.id,
            "name": e.name,
            "user_email": e.user_email,
            "tau": e.tau,
            "Vth": e.vth,
            "tSim": e.tsim,
            "stim": {
                "type": e.stim_type,
                "amplitude": e.amplitude,
                "pulseWidth": e.pulse_width,
                "pulseFreq": e.pulse_freq,
            },
            "neuro": {
                "gaba": e.gaba,
                "glu": e.glu,
            },
            "metrics": {
                "totalSpikes": e.total_spikes,
                "firingRateHz": e.firing_rate_hz,
                "meanVm": e.mean_vm,
                "peakVm": e.peak_vm,
            },
        }
        for e in experiments
    ]
@app.post("/experiments")
def save_experiment(payload: SaveExperimentRequest, db: Session = Depends(get_db)):
    # Find user
    user = (
        db.query(User)
        .filter(User.email == payload.user_email.lower())
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create new experiment
    exp = Experiment(
        name=payload.name,
        user_email=payload.user_email.lower(),

        tau=payload.tau,
        vth=payload.Vth,
        tsim=payload.tSim,

        stim_type=payload.stim.type,
        amplitude=payload.stim.amplitude,
        pulse_width=payload.stim.pulseWidth,
        pulse_freq=payload.stim.pulseFreq,

        gaba=payload.neuro.gaba,
        glu=payload.neuro.glu,

        total_spikes=payload.metrics.totalSpikes,
        firing_rate_hz=payload.metrics.firingRateHz,
        mean_vm=payload.metrics.meanVm,
        peak_vm=payload.metrics.peakVm,
    )

    db.add(exp)
    db.commit()
    db.refresh(exp)

    return {"message": "Experiment saved", "id": exp.id}

@app.get("/research/papers")
async def research_papers(
    region_terms: str = Query(...),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    year: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    query = f"{region_terms} {keyword}".strip()
    filters = ["has_abstract:true"]
    if year is not None:
        filters.append(f"publication_year:{year}")

    data = await openalex_search(
        search=query,
        page=page,
        per_page=8,
        sort="cited_by_count:desc",
        filters=",".join(filters),
    )
    return data


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
print("Anthropic key loaded:", bool(ANTHROPIC_API_KEY))
ANTHROPIC_CHAT_SYSTEM = (
    "You are the NeuroLIMS AI Assistant — an expert neuroscience guide and lab management assistant. "
    "Your responses adapt to the user's declared expertise level "
    "(1 = Undergraduate Student, 2 = Graduate Student, 3 = Postdoc Researcher, "
    "4 = PI / Senior Scientist, 5 = Clinician). "
    "On the very first user message, always ask for their expertise level before answering anything else, "
    "using this exact text: "
    "'Before we begin, what is your level of expertise in neuroscience? "
    "1 — Undergraduate Student (new to neuroscience, needs simple explanations), "
    "2 — Graduate Student (familiar with core concepts, some research experience), "
    "3 — Postdoctoral Researcher (deep domain knowledge, active researcher), "
    "4 — Principal Investigator / Senior Scientist (expert, leading research programs), "
    "5 — Clinician / Neurology Specialist (clinical neuroscience, patient-facing context). "
    "Please reply with a number (1–5).' "
    "Once the user replies with a number, acknowledge their level warmly, then adapt ALL future responses: "
    "Level 1: plain everyday language, analogies, short answers, encouraging tone, end with a fun fact or question. "
    "Level 2: standard terminology with brief explanations of advanced terms, include mechanisms, collegial tone. "
    "Level 3: full technical language, nuance and caveats, specific pathways/receptors/mechanisms, peer-to-peer tone. "
    "Level 4: maximally concise and information-dense, assume mastery, focus on strategy and translational angles, direct tone. "
    "Level 5: clinical framing, symptoms/diagnoses/treatment implications, ICD terminology where relevant, evidence-based tone. "
    "Never ask for the level again unless the user explicitly requests a change. "
    "If the user says 'change my level', 'switch to level X', or similar, update immediately and confirm. "
    "You also assist with the NeuroLIMS platform: sample tracking, protocols, assay results, study management, compliance. "
    "Apply the same expertise-level adaptation to all LIMS-related answers. "
    "Never use markdown formatting — no headers, no bold or italic symbols, no bullet points, no dashes as list markers, "
    "no numbered lists, no horizontal rules. Write everything as plain flowing sentences and paragraphs. "
    "Be accurate, professional, and scientifically rigorous at all levels — just adjust how you communicate, not the quality of information."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> Dict[str, str]:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured on server")

    messages = [{"role": m.role, "content": m.content} for m in payload.messages]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1000,
                    "system": ANTHROPIC_CHAT_SYSTEM,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("content", [{}])[0].get("text", "No response received.")
            return {"reply": reply}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Anthropic API error: {e.response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Chat service unavailable: {str(e)}")


@app.get("/research/studies")
async def research_studies(
    study_terms: str = Query(...),
    page: int = Query(default=1, ge=1),
    year: Optional[int] = Query(default=None),
) -> Dict[str, Any]:
    filters = ["has_abstract:true", "type:article"]
    if year is not None:
        filters.append(f"publication_year:{year}")

    data = await openalex_search(
        search=study_terms,
        page=page,
        per_page=8,
        sort="publication_date:desc",
        filters=",".join(filters),
    )
    return data