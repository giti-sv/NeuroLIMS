# Simulation Rules

## Goal
The NeuroLIMS simulation allows users to explore how selected brain regions respond to simple neurotransmitter and stimulation changes.

## Inputs
The user can:
- Select a brain region
- Select a neurotransmitter
- Select stimulation level: Low / Medium / High

## Core Logic
The simulation calculates:
- activity level
- learning/memory effect
- emotional effect
- motor effect
- warning state if overstimulation occurs

## Basic Rules

### Rule 1: Brain region selection
Each brain region has a primary function.

Examples:
- Hippocampus -> memory
- Amygdala -> emotion
- Occipital lobe -> vision
- Cerebellum -> coordination

### Rule 2: Neurotransmitter effect
- Glutamate increases activation
- GABA decreases activation
- Dopamine increases reward/motivation-related activity
- Serotonin stabilizes mood-related activity
- Acetylcholine supports attention and learning

### Rule 3: Stimulation level
- Low = small change
- Medium = moderate change
- High = strong change

### Rule 4: Output behavior
The app displays:
- neuron activity: low / normal / high
- functional effect: increased memory, calm response, visual processing boost, etc.
- warning if stimulation is too high

### Rule 5: Overstimulation
If stimulation is High and the excitatory effect is strong, show:
"Warning: This configuration may cause overstimulation in the selected brain region."
