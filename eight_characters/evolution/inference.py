from dataclasses import dataclass
from math import exp, inf, isinf, log
from typing import Sequence

import numpy as np

from eight_characters.evolution.energy import EnergyBreakdown, compute_energy_breakdown
from eight_characters.evolution.families import (
    FamilyEvaluation,
    evaluate_all_families,
    family_spec,
)
from eight_characters.evolution.mechanics import compute_dynamic_vitality_amplitudes
from eight_characters.evolution.primitives import OMEGA_MIN_R, season_element_from_month_branch
from eight_characters.evolution.state import (
    FullTransformationCapture,
    LatentState,
    ObservedState,
    RULE_STATE_DOMAINS,
    VALID_MODES,
    recompute_effective_ten_gods,
    resolve_effective_elements,
)


@dataclass(frozen=True)
class InferenceConfig:
    particles: int = 1000
    temperature_steps: int = 50
    omega_start: float = 10.0
    omega_end: float = 1.0
    ess_threshold_ratio: float = 0.5
    sweeps_per_step: int = 5
    continuous_sigma: float = 0.1
    seed: int = 42

    def validate(self) -> None:
        if self.particles <= 0:
            raise ValueError('particles must be positive')
        if self.temperature_steps <= 0:
            raise ValueError('temperature_steps must be positive')
        if self.omega_start <= 0.0 or self.omega_end <= 0.0:
            raise ValueError('omega_start and omega_end must be positive')
        if self.ess_threshold_ratio <= 0.0 or self.ess_threshold_ratio > 1.0:
            raise ValueError('ess_threshold_ratio must be in (0,1]')
        if self.sweeps_per_step <= 0:
            raise ValueError('sweeps_per_step must be positive')
        if self.continuous_sigma <= 0.0:
            raise ValueError('continuous_sigma must be positive')


@dataclass(frozen=True)
class ParticleSnapshot:
    latent_state: LatentState
    effective_elements: tuple[tuple[int, int, int, int, int], ...]
    effective_ten_gods: tuple[tuple[int, ...], ...]
    dynamic_amplitudes: tuple[float, ...]
    energy_breakdown: EnergyBreakdown


@dataclass(frozen=True)
class InferenceResult:
    particles: tuple[ParticleSnapshot, ...]
    weights: tuple[float, ...]
    temperature_ladder: tuple[float, ...]
    ess_history: tuple[float, ...]
    weight_sum_history: tuple[float, ...]
    resample_steps: tuple[int, ...]


def temperature_ladder(config: InferenceConfig) -> tuple[float, ...]:
    config.validate()
    ratio = config.omega_end / config.omega_start
    return tuple(
        config.omega_start * (ratio ** (step / config.temperature_steps))
        for step in range(config.temperature_steps + 1)
    )


def _omega_bounds(
    evaluations: Sequence[FamilyEvaluation],
) -> tuple[tuple[float, float], ...]:
    bounds: list[tuple[float, float]] = []
    for evaluation in evaluations:
        omega_max = 1.0 + evaluation.proximity_weight
        bounds.append((OMEGA_MIN_R, omega_max))
    return tuple(bounds)


def _full_captures_from_latent(
    latent_state: LatentState,
    evaluations: Sequence[FamilyEvaluation],
) -> tuple[FullTransformationCapture, ...]:
    captures: list[FullTransformationCapture] = []
    for evaluation in evaluations:
        rule_index = evaluation.rule_index
        # Full transformation capture is applied only to stem combinations and six harmonies.
        if rule_index > 11:
            continue
        spec = family_spec(rule_index)
        if spec.target_element_index is None:
            continue
        full_state = max(spec.state_domain)
        if latent_state.switches[rule_index - 1] != full_state:
            continue
        for entity_index in evaluation.q_entity_indices:
            captures.append(
                FullTransformationCapture(
                    rule_index=rule_index,
                    entity_index=entity_index,
                    target_element_index=spec.target_element_index,
                )
            )
    return tuple(captures)


def _damage_participation_maps(
    latent_state: LatentState,
    evaluations: Sequence[FamilyEvaluation],
) -> tuple[dict[tuple[int, int], float], dict[tuple[int, int], float]]:
    clash_map: dict[tuple[int, int], float] = {}
    punishment_map: dict[tuple[int, int], float] = {}
    for evaluation in evaluations:
        rule_index = evaluation.rule_index
        switch_value = latent_state.switches[rule_index - 1]

        if 12 <= rule_index <= 17 and switch_value == 1:
            for entity_index in evaluation.q_entity_indices:
                clash_map[(rule_index, entity_index)] = 1.0

        if 22 <= rule_index <= 28 and switch_value > 0:
            for entity_index in evaluation.q_entity_indices:
                punishment_map[(rule_index, entity_index)] = 1.0

    return clash_map, punishment_map


def _build_particle(
    observed_state: ObservedState,
    latent_state: LatentState,
    evaluations: Sequence[FamilyEvaluation],
    season_element_index: int,
) -> ParticleSnapshot:
    full_captures = _full_captures_from_latent(latent_state, evaluations)
    try:
        effective_elements = resolve_effective_elements(
            observed_state=observed_state,
            full_captures=full_captures,
        )
    except ValueError:
        # Exclusivity conflict; let energy evaluator return +inf.
        effective_elements = observed_state.base_elements

    effective_ten_gods = recompute_effective_ten_gods(
        observed_state=observed_state,
        effective_elements=effective_elements,
        mode=latent_state.mode,
    )

    clash_map, punishment_map = _damage_participation_maps(
        latent_state=latent_state,
        evaluations=evaluations,
    )
    dynamic_amplitudes = compute_dynamic_vitality_amplitudes(
        observed_state=observed_state,
        latent_state=latent_state,
        clash_participation=clash_map,
        punishment_participation=punishment_map,
    )

    energy_breakdown = compute_energy_breakdown(
        observed_state=observed_state,
        latent_state=latent_state,
        effective_elements=effective_elements,
        effective_ten_gods=effective_ten_gods,
        dynamic_amplitudes=dynamic_amplitudes,
        family_evaluations=evaluations,
        season_element_index=season_element_index,
        full_captures=full_captures,
    )

    return ParticleSnapshot(
        latent_state=latent_state,
        effective_elements=effective_elements,
        effective_ten_gods=effective_ten_gods,
        dynamic_amplitudes=dynamic_amplitudes,
        energy_breakdown=energy_breakdown,
    )


def _systematic_resample_indices(
    weights: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    n = weights.size
    positions = (rng.random() + np.arange(n, dtype=np.float64)) / n
    cumulative = np.cumsum(weights, dtype=np.float64)
    return np.searchsorted(cumulative, positions, side='left')


def _mh_accept(
    current_energy: float,
    proposed_energy: float,
    temperature: float,
    rng: np.random.Generator,
) -> bool:
    if isinf(proposed_energy):
        return False
    if proposed_energy <= current_energy:
        return True
    log_alpha = -(proposed_energy - current_energy) / temperature
    return log(rng.random()) < log_alpha


def _propose_discrete(
    particle: ParticleSnapshot,
    observed_state: ObservedState,
    evaluations: Sequence[FamilyEvaluation],
    season_element_index: int,
    rng: np.random.Generator,
    temperature: float,
) -> ParticleSnapshot:
    pick = int(rng.integers(0, 35))  # 0 => mode, 1..34 => switches
    current_latent = particle.latent_state

    if pick == 0:
        candidate_modes = [mode for mode in VALID_MODES if mode != current_latent.mode]
        candidate_mode = candidate_modes[int(rng.integers(0, len(candidate_modes)))]
        proposal = LatentState(
            switches=current_latent.switches,
            omegas=current_latent.omegas,
            mode=candidate_mode,
        )
    else:
        rule_index = pick
        current_value = current_latent.switches[rule_index - 1]
        domain = RULE_STATE_DOMAINS[rule_index - 1]
        candidate_values = [value for value in domain if value != current_value]
        proposal_value = candidate_values[int(rng.integers(0, len(candidate_values)))]

        if evaluations[rule_index - 1].applicability == 0 and proposal_value > 0:
            return particle

        switches = list(current_latent.switches)
        switches[rule_index - 1] = proposal_value
        proposal = LatentState(
            switches=tuple(switches),
            omegas=current_latent.omegas,
            mode=current_latent.mode,
        )

    try:
        candidate = _build_particle(
            observed_state=observed_state,
            latent_state=proposal,
            evaluations=evaluations,
            season_element_index=season_element_index,
        )
    except ValueError:
        return particle

    if _mh_accept(
        current_energy=particle.energy_breakdown.total,
        proposed_energy=candidate.energy_breakdown.total,
        temperature=temperature,
        rng=rng,
    ):
        return candidate
    return particle


def _propose_continuous(
    particle: ParticleSnapshot,
    observed_state: ObservedState,
    evaluations: Sequence[FamilyEvaluation],
    season_element_index: int,
    omega_bounds: Sequence[tuple[float, float]],
    sigma: float,
    rng: np.random.Generator,
    temperature: float,
) -> ParticleSnapshot:
    rule_index = int(rng.integers(1, 35))
    lower, upper = omega_bounds[rule_index - 1]
    current_omega = particle.latent_state.omegas[rule_index - 1]
    candidate_omega = float(rng.normal(current_omega, sigma))
    if candidate_omega < lower or candidate_omega > upper:
        return particle

    omegas = list(particle.latent_state.omegas)
    omegas[rule_index - 1] = candidate_omega
    proposal = LatentState(
        switches=particle.latent_state.switches,
        omegas=tuple(omegas),
        mode=particle.latent_state.mode,
    )

    try:
        candidate = _build_particle(
            observed_state=observed_state,
            latent_state=proposal,
            evaluations=evaluations,
            season_element_index=season_element_index,
        )
    except ValueError:
        return particle

    if _mh_accept(
        current_energy=particle.energy_breakdown.total,
        proposed_energy=candidate.energy_breakdown.total,
        temperature=temperature,
        rng=rng,
    ):
        return candidate
    return particle


def _initial_particle(
    observed_state: ObservedState,
    evaluations: Sequence[FamilyEvaluation],
    season_element_index: int,
    rng: np.random.Generator,
) -> ParticleSnapshot:
    # Start from structurally valid dormant topology, with randomized global mode.
    mode = VALID_MODES[int(rng.integers(0, len(VALID_MODES)))]
    latent_state = LatentState(
        switches=tuple(0 for _ in range(34)),
        omegas=tuple(OMEGA_MIN_R for _ in range(34)),
        mode=mode,
    )
    return _build_particle(
        observed_state=observed_state,
        latent_state=latent_state,
        evaluations=evaluations,
        season_element_index=season_element_index,
    )


def run_tempered_smc(
    observed_state: ObservedState,
    config: InferenceConfig | None = None,
) -> InferenceResult:
    observed_state.validate()
    cfg = config or InferenceConfig()
    cfg.validate()

    evaluations = evaluate_all_families(observed_state)
    season_element = season_element_from_month_branch(observed_state.branch_ids[1])
    omega_bounds = _omega_bounds(evaluations)

    rng = np.random.Generator(np.random.PCG64(cfg.seed))
    ladder = temperature_ladder(cfg)

    particles = [
        _initial_particle(observed_state, evaluations, season_element, rng)
        for _ in range(cfg.particles)
    ]
    weights = np.full(cfg.particles, 1.0 / cfg.particles, dtype=np.float64)

    ess_history: list[float] = [float(1.0 / np.sum(np.square(weights)))]
    weight_sum_history: list[float] = [float(np.sum(weights))]
    resample_steps: list[int] = []

    for step in range(1, len(ladder)):
        previous_temp = ladder[step - 1]
        current_temp = ladder[step]
        delta = (1.0 / current_temp) - (1.0 / previous_temp)

        energies = np.array(
            [particle.energy_breakdown.total for particle in particles],
            dtype=np.float64,
        )
        increments = np.exp(-energies * delta, dtype=np.float64)
        weights = weights * increments

        weight_sum = float(np.sum(weights))
        if weight_sum <= 0.0 or isinf(weight_sum):
            weights = np.full(cfg.particles, 1.0 / cfg.particles, dtype=np.float64)
        else:
            weights = weights / weight_sum

        # Required by spec: normalize after every reweighting step.
        normalized_sum = float(np.sum(weights))
        weight_sum_history.append(normalized_sum)

        ess = float(1.0 / np.sum(np.square(weights)))
        if ess < cfg.particles * cfg.ess_threshold_ratio:
            indices = _systematic_resample_indices(weights, rng)
            particles = [particles[int(index)] for index in indices]
            weights = np.full(cfg.particles, 1.0 / cfg.particles, dtype=np.float64)
            resample_steps.append(step)
            ess = float(1.0 / np.sum(np.square(weights)))

        for _ in range(cfg.sweeps_per_step):
            for idx in range(cfg.particles):
                particle = particles[idx]
                particle = _propose_discrete(
                    particle=particle,
                    observed_state=observed_state,
                    evaluations=evaluations,
                    season_element_index=season_element,
                    rng=rng,
                    temperature=current_temp,
                )
                particle = _propose_continuous(
                    particle=particle,
                    observed_state=observed_state,
                    evaluations=evaluations,
                    season_element_index=season_element,
                    omega_bounds=omega_bounds,
                    sigma=cfg.continuous_sigma,
                    rng=rng,
                    temperature=current_temp,
                )
                # Enforce deterministic recomputation step after proposals.
                particle = _build_particle(
                    observed_state=observed_state,
                    latent_state=particle.latent_state,
                    evaluations=evaluations,
                    season_element_index=season_element,
                )
                particles[idx] = particle

        ess_history.append(float(1.0 / np.sum(np.square(weights))))

    return InferenceResult(
        particles=tuple(particles),
        weights=tuple(float(value) for value in weights),
        temperature_ladder=tuple(float(value) for value in ladder),
        ess_history=tuple(ess_history),
        weight_sum_history=tuple(weight_sum_history),
        resample_steps=tuple(resample_steps),
    )

