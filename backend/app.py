from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import os

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
def login(payload: AuthRequest) -> Dict[str, str]:
    for user in USERS:
        if user["email"].lower() == payload.email.lower() and user["password"] == payload.password:
            return {"name": user["name"], "email": user["email"]}
    raise HTTPException(status_code=401, detail="Invalid email or password")


@app.post("/auth/register", response_model=UserResponse)
def register(payload: RegisterRequest) -> Dict[str, str]:
    if any(u["email"].lower() == payload.email.lower() for u in USERS):
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = {
        "name": payload.name,
        "email": payload.email,
        "password": payload.password,
    }
    USERS.append(new_user)
    return {"name": new_user["name"], "email": new_user["email"]}


@app.post("/simulate", response_model=SimulationResult)
def simulate(payload: SimulationInput) -> Dict[str, Any]:
    return lif_simulation(payload)


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