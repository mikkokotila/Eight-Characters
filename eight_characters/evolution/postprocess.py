from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

import numpy as np

from eight_characters.evolution.families import FamilyEvaluation, evaluate_all_families
from eight_characters.evolution.inference import (
    InferenceResult,
    ParticleSnapshot,
    build_particle,
)
from eight_characters.evolution.mechanics import realized_flux
from eight_characters.evolution.primitives import (
    CLUSTER_ALPHA,
    CLUSTER_BETA,
    CLUSTER_GAMMA,
    DBSCAN_EPS,
    DBSCAN_MIN_SAMPLES,
    EPSILON,
    OMEGA_MIN_R,
    season_element_from_month_branch,
)
from eight_characters.evolution.state import (
    RULE_COUNT,
    RULE_STATE_DOMAINS,
    VALID_MODES,
    LatentState,
    ObservedState,
)


@dataclass(frozen=True)
class PostprocessConfig:
    discrete_relax_max_passes: int = 100
    continuous_delta: float = 1.0e-3
    continuous_learning_rate: float = 0.05
    continuous_passes: int = 50
    dbscan_eps: float = DBSCAN_EPS
    dbscan_min_samples: int = DBSCAN_MIN_SAMPLES

    def validate(self) -> None:
        if self.discrete_relax_max_passes <= 0:
            raise ValueError('discrete_relax_max_passes must be positive')
        if self.continuous_delta <= 0:
            raise ValueError('continuous_delta must be positive')
        if self.continuous_learning_rate <= 0:
            raise ValueError('continuous_learning_rate must be positive')
        if self.continuous_passes <= 0:
            raise ValueError('continuous_passes must be positive')
        if self.dbscan_eps <= 0:
            raise ValueError('dbscan_eps must be positive')
        if self.dbscan_min_samples <= 0:
            raise ValueError('dbscan_min_samples must be positive')


@dataclass(frozen=True)
class MotifInventory:
    chains: tuple[tuple[int, ...], ...]
    loops: tuple[tuple[int, ...], ...]
    pulses: tuple[int, ...]
    cascades: tuple[tuple[int, ...], ...]
    absences: tuple[int, ...]
    bottlenecks: tuple[int, ...]


@dataclass(frozen=True)
class BasinSummary:
    basin_id: int
    mass: float
    map_particle_index: int
    mode: str
    chart_temperature: float
    chart_saturation: float
    motif_inventory: MotifInventory


@dataclass(frozen=True)
class PostprocessResult:
    basins: tuple[BasinSummary, ...]
    noise_probability: float
    labels: tuple[int, ...]
    relaxed_particles: tuple[ParticleSnapshot, ...]


def _omega_bounds(
    evaluations: Sequence[FamilyEvaluation],
) -> tuple[tuple[float, float], ...]:
    return tuple(
        (OMEGA_MIN_R, 1.0 + evaluation.proximity_weight) for evaluation in evaluations
    )


def _distance(
    particle_a: ParticleSnapshot,
    particle_b: ParticleSnapshot,
    omega_bounds: Sequence[tuple[float, float]],
) -> float:
    switches_a = particle_a.latent_state.switches
    switches_b = particle_b.latent_state.switches
    mode_a = particle_a.latent_state.mode
    mode_b = particle_b.latent_state.mode

    d_h_switch = sum(1 for left, right in zip(switches_a, switches_b) if left != right)
    mode_gap = 1 if mode_a != mode_b else 0

    d_h_effective = sum(
        1
        for left, right in zip(
            particle_a.effective_elements,
            particle_b.effective_elements,
        )
        if left != right
    )

    cont_sum = 0.0
    for idx in range(RULE_COUNT):
        left_active = switches_a[idx] > 0
        right_active = switches_b[idx] > 0
        if not (left_active or right_active):
            continue
        lower, upper = omega_bounds[idx]
        denom = max(upper - lower, EPSILON)
        cont_sum += (
            abs(
                particle_a.latent_state.omegas[idx]
                - particle_b.latent_state.omegas[idx]
            )
            / denom
        )

    return (
        CLUSTER_ALPHA * (d_h_switch + mode_gap) / float(RULE_COUNT + 1)
        + CLUSTER_BETA * d_h_effective / 16.0
        + CLUSTER_GAMMA * (cont_sum / float(RULE_COUNT))
    )


def _distance_matrix(
    particles: Sequence[ParticleSnapshot],
    omega_bounds: Sequence[tuple[float, float]],
) -> np.ndarray:
    size = len(particles)
    matrix = np.zeros((size, size), dtype=np.float64)
    for left in range(size):
        for right in range(left + 1, size):
            value = _distance(particles[left], particles[right], omega_bounds)
            matrix[left, right] = value
            matrix[right, left] = value
    return matrix


def _dbscan_labels(
    distance_matrix: np.ndarray,
    eps: float,
    min_samples: int,
) -> list[int]:
    unvisited = -99
    noise = -1
    labels = [unvisited] * len(distance_matrix)

    def neighbors(index: int) -> list[int]:
        return [
            other for other, dist in enumerate(distance_matrix[index]) if dist <= eps
        ]

    cluster_id = 0
    for index in range(len(distance_matrix)):
        if labels[index] != unvisited:
            continue
        nbs = neighbors(index)
        if len(nbs) < min_samples:
            labels[index] = noise
            continue

        labels[index] = cluster_id
        seeds = [node for node in nbs if node != index]
        seed_seen = set(seeds)
        cursor = 0
        while cursor < len(seeds):
            node = seeds[cursor]
            if labels[node] == noise:
                labels[node] = cluster_id
            if labels[node] != unvisited:
                cursor += 1
                continue

            labels[node] = cluster_id
            node_neighbors = neighbors(node)
            if len(node_neighbors) >= min_samples:
                for candidate in node_neighbors:
                    if candidate in seed_seen:
                        continue
                    seeds.append(candidate)
                    seed_seen.add(candidate)
            cursor += 1

        cluster_id += 1

    return labels


def _active_edges(
    flux_matrix: Sequence[Sequence[float]],
) -> tuple[float, list[tuple[int, int, float]]]:
    nonzero = [abs(value) for row in flux_matrix for value in row if value != 0.0]
    if not nonzero:
        return 0.0, []
    threshold = 0.25 * max(nonzero)
    edges: list[tuple[int, int, float]] = []
    for source in range(len(flux_matrix)):
        for target in range(len(flux_matrix)):
            value = flux_matrix[source][target]
            if abs(value) >= threshold and value != 0.0:
                edges.append((source, target, value))
    return threshold, edges


def _motifs_for_particle(
    observed_state: ObservedState,
    particle: ParticleSnapshot,
) -> MotifInventory:
    flux = realized_flux(
        observed_state=observed_state,
        effective_elements=particle.effective_elements,
        dynamic_amplitudes=particle.dynamic_amplitudes,
    )
    _, edges = _active_edges(flux)
    if not edges:
        absences = tuple(
            element_idx
            for element_idx in range(5)
            if sum(
                observed_state.masks[i]
                * int(particle.effective_elements[i][element_idx] == 1)
                for i in range(len(particle.effective_elements))
            )
            == 0
        )
        return MotifInventory(
            chains=(),
            loops=(),
            pulses=(),
            cascades=(),
            absences=absences,
            bottlenecks=(),
        )

    adjacency: dict[int, list[int]] = {}
    edge_value: dict[tuple[int, int], float] = {}
    for source, target, value in edges:
        adjacency.setdefault(source, []).append(target)
        edge_value[(source, target)] = value

    absences = tuple(
        element_idx
        for element_idx in range(5)
        if sum(
            observed_state.masks[i]
            * int(particle.effective_elements[i][element_idx] == 1)
            for i in range(len(particle.effective_elements))
        )
        == 0
    )

    chains_set: set[tuple[int, ...]] = set()

    def walk_chain(path: tuple[int, ...], sign: int | None) -> None:
        current = path[-1]
        next_nodes = adjacency.get(current, [])
        extension_found = False
        for nxt in next_nodes:
            if nxt in path:
                continue
            value = edge_value[(current, nxt)]
            edge_sign = 1 if value > 0 else -1
            if sign is not None and edge_sign != sign:
                continue
            extension_found = True
            walk_chain((*path, nxt), edge_sign if sign is None else sign)
        if not extension_found and len(path) >= 3:
            chains_set.add(path)

    for start in range(len(flux)):
        walk_chain((start,), None)

    chains = tuple(sorted(chains_set))

    loops_set: set[tuple[int, ...]] = set()

    def dfs_cycle(start: int, current: int, path: tuple[int, ...]) -> None:
        for nxt in adjacency.get(current, []):
            if nxt == start and len(path) >= 2:
                cycle = path
                min_idx = min(range(len(cycle)), key=lambda idx: cycle[idx])
                canonical = cycle[min_idx:] + cycle[:min_idx]
                loops_set.add(canonical)
                continue
            if nxt in path:
                continue
            dfs_cycle(start, nxt, (*path, nxt))

    for node in range(len(flux)):
        dfs_cycle(node, node, (node,))

    loops = tuple(sorted(loops_set))

    inbound = [0.0] * len(flux)
    outbound = [0.0] * len(flux)
    for source, target, value in edges:
        outbound[source] += abs(value)
        inbound[target] += abs(value)
    throughput = [inbound[idx] + outbound[idx] for idx in range(len(flux))]
    nonzero_throughput = [value for value in throughput if value > 0.0]
    med = median(nonzero_throughput) if nonzero_throughput else 0.0
    pulses = tuple(
        idx
        for idx in range(len(flux))
        if inbound[idx] > med
        and outbound[idx] > med
        and 0.5 <= inbound[idx] / (outbound[idx] + EPSILON) <= 2.0
    )

    cascades: list[tuple[int, ...]] = []
    for chain in chains:
        magnitudes = [
            abs(edge_value[(chain[idx], chain[idx + 1])])
            for idx in range(len(chain) - 1)
        ]
        if (
            all(
                magnitudes[idx + 1] >= magnitudes[idx]
                for idx in range(len(magnitudes) - 1)
            )
            and magnitudes[-1] / (magnitudes[0] + EPSILON) >= 1.25
        ):
            cascades.append(chain)

    b_values: list[float] = []
    for idx in range(len(flux)):
        score = (inbound[idx] + outbound[idx]) / (
            particle.dynamic_amplitudes[idx] + EPSILON
        )
        b_values.append(score)
    quartile = float(np.quantile(np.array(b_values, dtype=np.float64), 0.75))
    bottlenecks = tuple(idx for idx, value in enumerate(b_values) if value >= quartile)

    return MotifInventory(
        chains=chains,
        loops=loops,
        pulses=pulses,
        cascades=tuple(cascades),
        absences=absences,
        bottlenecks=bottlenecks,
    )


def _active_omega_l2(latent_state: LatentState) -> float:
    return (
        sum(
            omega * omega
            for omega, switch in zip(latent_state.omegas, latent_state.switches)
            if switch > 0
        )
        ** 0.5
    )


def _try_build(
    observed_state: ObservedState,
    latent_state: LatentState,
    evaluations: Sequence[FamilyEvaluation],
    season_element: int,
) -> ParticleSnapshot | None:
    try:
        return build_particle(
            observed_state=observed_state,
            latent_state=latent_state,
            evaluations=evaluations,
            season_element_index=season_element,
        )
    except ValueError:
        return None


def _discrete_relax(
    observed_state: ObservedState,
    particle: ParticleSnapshot,
    evaluations: Sequence[FamilyEvaluation],
    season_element: int,
    max_passes: int,
) -> ParticleSnapshot:
    current = particle
    for _ in range(max_passes):
        changed = False

        # Mode first.
        best_candidate = current
        best_delta = 0.0
        for mode in VALID_MODES:
            if mode == current.latent_state.mode:
                continue
            candidate_latent = LatentState(
                switches=current.latent_state.switches,
                omegas=current.latent_state.omegas,
                mode=mode,
            )
            candidate = _try_build(
                observed_state, candidate_latent, evaluations, season_element
            )
            if candidate is None:
                continue
            delta = candidate.energy_breakdown.total - current.energy_breakdown.total
            if delta < best_delta:
                best_delta = delta
                best_candidate = candidate
        if best_candidate is not current:
            current = best_candidate
            changed = True

        # Then rule switches in order 1..34.
        for rule_index in range(1, RULE_COUNT + 1):
            current_value = current.latent_state.switches[rule_index - 1]
            domain = RULE_STATE_DOMAINS[rule_index - 1]
            best_candidate = current
            best_delta = 0.0
            for candidate_value in domain:
                if candidate_value == current_value:
                    continue
                switches = list(current.latent_state.switches)
                switches[rule_index - 1] = candidate_value
                candidate_latent = LatentState(
                    switches=tuple(switches),
                    omegas=current.latent_state.omegas,
                    mode=current.latent_state.mode,
                )
                candidate = _try_build(
                    observed_state=observed_state,
                    latent_state=candidate_latent,
                    evaluations=evaluations,
                    season_element=season_element,
                )
                if candidate is None:
                    continue
                delta = (
                    candidate.energy_breakdown.total - current.energy_breakdown.total
                )
                if delta < best_delta:
                    best_delta = delta
                    best_candidate = candidate
            if best_candidate is not current:
                current = best_candidate
                changed = True

        if not changed:
            break
    return current


def _continuous_relax(
    observed_state: ObservedState,
    particle: ParticleSnapshot,
    evaluations: Sequence[FamilyEvaluation],
    season_element: int,
    omega_bounds: Sequence[tuple[float, float]],
    delta: float,
    learning_rate: float,
    passes: int,
) -> ParticleSnapshot:
    current = particle
    for _ in range(passes):
        active_rules = [
            rule_index
            for rule_index, switch in enumerate(current.latent_state.switches, start=1)
            if switch > 0
        ]
        for rule_index in active_rules:
            lower, upper = omega_bounds[rule_index - 1]
            base = current.latent_state.omegas[rule_index - 1]
            plus = min(base + delta, upper)
            minus = max(base - delta, lower)
            if plus == minus:
                continue

            omegas_plus = list(current.latent_state.omegas)
            omegas_plus[rule_index - 1] = plus
            particle_plus = _try_build(
                observed_state=observed_state,
                latent_state=LatentState(
                    switches=current.latent_state.switches,
                    omegas=tuple(omegas_plus),
                    mode=current.latent_state.mode,
                ),
                evaluations=evaluations,
                season_element=season_element,
            )
            if particle_plus is None:
                continue

            omegas_minus = list(current.latent_state.omegas)
            omegas_minus[rule_index - 1] = minus
            particle_minus = _try_build(
                observed_state=observed_state,
                latent_state=LatentState(
                    switches=current.latent_state.switches,
                    omegas=tuple(omegas_minus),
                    mode=current.latent_state.mode,
                ),
                evaluations=evaluations,
                season_element=season_element,
            )
            if particle_minus is None:
                continue

            grad = (
                particle_plus.energy_breakdown.total
                - particle_minus.energy_breakdown.total
            ) / max(plus - minus, EPSILON)
            proposal_omega = max(lower, min(upper, base - learning_rate * grad))
            omegas_proposal = list(current.latent_state.omegas)
            omegas_proposal[rule_index - 1] = proposal_omega
            candidate = _try_build(
                observed_state=observed_state,
                latent_state=LatentState(
                    switches=current.latent_state.switches,
                    omegas=tuple(omegas_proposal),
                    mode=current.latent_state.mode,
                ),
                evaluations=evaluations,
                season_element=season_element,
            )
            if candidate is None:
                continue
            current = candidate
    return current


def postprocess_inference(
    observed_state: ObservedState,
    inference_result: InferenceResult,
    config: PostprocessConfig | None = None,
) -> PostprocessResult:
    observed_state.validate()
    cfg = config or PostprocessConfig()
    cfg.validate()

    particles = list(inference_result.particles)
    weights = list(inference_result.weights)
    if len(particles) != len(weights):
        raise ValueError('particles and weights length mismatch')

    evaluations = evaluate_all_families(observed_state)
    omega_bounds = _omega_bounds(evaluations)
    season_element = season_element_from_month_branch(observed_state.branch_ids[1])

    relaxed_particles = [
        _continuous_relax(
            observed_state=observed_state,
            particle=_discrete_relax(
                observed_state=observed_state,
                particle=particle,
                evaluations=evaluations,
                season_element=season_element,
                max_passes=cfg.discrete_relax_max_passes,
            ),
            evaluations=evaluations,
            season_element=season_element,
            omega_bounds=omega_bounds,
            delta=cfg.continuous_delta,
            learning_rate=cfg.continuous_learning_rate,
            passes=cfg.continuous_passes,
        )
        for particle in particles
    ]

    distance_matrix = _distance_matrix(relaxed_particles, omega_bounds)
    labels = _dbscan_labels(
        distance_matrix=distance_matrix,
        eps=cfg.dbscan_eps,
        min_samples=cfg.dbscan_min_samples,
    )

    basin_ids = sorted({label for label in labels if label >= 0})
    basins: list[BasinSummary] = []
    total_basin_mass = 0.0
    for basin_id in basin_ids:
        members = [idx for idx, label in enumerate(labels) if label == basin_id]
        basin_mass = sum(weights[idx] for idx in members)
        total_basin_mass += basin_mass

        map_index = min(
            members,
            key=lambda idx: (
                relaxed_particles[idx].energy_breakdown.total,
                _active_omega_l2(relaxed_particles[idx].latent_state),
            ),
        )
        map_particle = relaxed_particles[map_index]
        motifs = _motifs_for_particle(observed_state, map_particle)

        basins.append(
            BasinSummary(
                basin_id=basin_id,
                mass=basin_mass,
                map_particle_index=map_index,
                mode=map_particle.latent_state.mode,
                chart_temperature=map_particle.energy_breakdown.chart_temperature,
                chart_saturation=map_particle.energy_breakdown.chart_saturation,
                motif_inventory=motifs,
            )
        )

    noise_probability = 1.0 - total_basin_mass
    return PostprocessResult(
        basins=tuple(basins),
        noise_probability=noise_probability,
        labels=tuple(labels),
        relaxed_particles=tuple(relaxed_particles),
    )
