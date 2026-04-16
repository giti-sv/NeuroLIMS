from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./neurolims.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

    experiments = relationship("Experiment", back_populates="user", cascade="all, delete-orphan")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)

    tau = Column(Float, nullable=False)
    vth = Column(Float, nullable=False)
    tsim = Column(Float, nullable=False)

    stim_type = Column(String, nullable=False)
    amplitude = Column(Float, nullable=False)
    pulse_width = Column(Float, nullable=False)
    pulse_freq = Column(Float, nullable=False)

    gaba = Column(Float, nullable=False)
    glu = Column(Float, nullable=False)

    total_spikes = Column(Integer, nullable=False)
    firing_rate_hz = Column(Float, nullable=False)
    mean_vm = Column(Float, nullable=False)
    peak_vm = Column(Float, nullable=False)

    user = relationship("User", back_populates="experiments")


def init_db():
    Base.metadata.create_all(bind=engine)