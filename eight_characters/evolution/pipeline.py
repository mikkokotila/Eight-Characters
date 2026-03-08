from dataclasses import dataclass

from eight_characters.evolution.inference import (
    InferenceConfig,
    run_tempered_smc,
)
from eight_characters.evolution.postprocess import (
    MotifInventory,
    PostprocessConfig,
    postprocess_inference,
)
from eight_characters.evolution.state import ObservedState


@dataclass(frozen=True)
class EvolutionInput:
    branch_ids: tuple[int, int, int, int]
    base_elements: tuple[tuple[int, int, int, int, int], ...]
    polarities: tuple[int, ...]
    hierarchy_levels: tuple[int, ...]
    positions: tuple[int, ...]
    masks: tuple[int, ...]
    vitality_stages: tuple[int, ...]
    day_master_index: int

    def to_observed_state(self) -> ObservedState:
        state = ObservedState(
            branch_ids=self.branch_ids,
            base_elements=self.base_elements,
            polarities=self.polarities,
            hierarchy_levels=self.hierarchy_levels,
            positions=self.positions,
            masks=self.masks,
            vitality_stages=self.vitality_stages,
            day_master_index=self.day_master_index,
        )
        state.validate()
        return state

    @classmethod
    def from_observed_state(cls, observed_state: ObservedState) -> 'EvolutionInput':
        observed_state.validate()
        return cls(
            branch_ids=observed_state.branch_ids,
            base_elements=observed_state.base_elements,
            polarities=observed_state.polarities,
            hierarchy_levels=observed_state.hierarchy_levels,
            positions=observed_state.positions,
            masks=observed_state.masks,
            vitality_stages=observed_state.vitality_stages,
            day_master_index=observed_state.day_master_index,
        )


@dataclass(frozen=True)
class BasinOutput:
    basin_id: int
    mass: float
    mode: str
    chart_temperature: float
    chart_saturation: float
    motifs: MotifInventory
    map_total_energy: float
    map_switches: tuple[int, ...]
    map_omegas: tuple[float, ...]
    map_effective_elements: tuple[tuple[int, int, int, int, int], ...]
    map_effective_ten_gods: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class EvolutionOutput:
    input_shape: EvolutionInput
    basins: tuple[BasinOutput, ...]
    noise_probability: float
    particle_count: int
    labels: tuple[int, ...]
    temperature_ladder: tuple[float, ...]
    ess_history: tuple[float, ...]
    weight_sum_history: tuple[float, ...]
    resample_steps: tuple[int, ...]


def run_natal_mvp(
    evolution_input: EvolutionInput,
    inference_config: InferenceConfig | None = None,
    postprocess_config: PostprocessConfig | None = None,
) -> EvolutionOutput:
    observed_state = evolution_input.to_observed_state()
    inference_result = run_tempered_smc(
        observed_state=observed_state,
        config=inference_config,
    )
    postprocess_result = postprocess_inference(
        observed_state=observed_state,
        inference_result=inference_result,
        config=postprocess_config,
    )

    basin_outputs: list[BasinOutput] = []
    for basin in postprocess_result.basins:
        map_particle = postprocess_result.relaxed_particles[basin.map_particle_index]
        basin_outputs.append(
            BasinOutput(
                basin_id=basin.basin_id,
                mass=basin.mass,
                mode=basin.mode,
                chart_temperature=basin.chart_temperature,
                chart_saturation=basin.chart_saturation,
                motifs=basin.motif_inventory,
                map_total_energy=map_particle.energy_breakdown.total,
                map_switches=map_particle.latent_state.switches,
                map_omegas=map_particle.latent_state.omegas,
                map_effective_elements=map_particle.effective_elements,
                map_effective_ten_gods=map_particle.effective_ten_gods,
            )
        )

    return EvolutionOutput(
        input_shape=evolution_input,
        basins=tuple(basin_outputs),
        noise_probability=postprocess_result.noise_probability,
        particle_count=len(inference_result.particles),
        labels=postprocess_result.labels,
        temperature_ladder=inference_result.temperature_ladder,
        ess_history=inference_result.ess_history,
        weight_sum_history=inference_result.weight_sum_history,
        resample_steps=inference_result.resample_steps,
    )
