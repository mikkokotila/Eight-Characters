from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleContract:
    name: str
    responsibility: str
    dependencies: tuple[str, ...]


MODULE_CONTRACTS: dict[str, ModuleContract] = {
    'conventions': ModuleContract(
        name='conventions',
        responsibility='Convention configuration defaults and validation.',
        dependencies=(),
    ),
    'policy': ModuleContract(
        name='policy',
        responsibility='Scope and decision policy enforcement.',
        dependencies=('conventions',),
    ),
    'time_convert': ModuleContract(
        name='time_convert',
        responsibility='Civil time to UTC and UTC to TT routing pipeline.',
        dependencies=('policy',),
    ),
    'vsop87d': ModuleContract(
        name='vsop87d',
        responsibility='VSOP87D Earth series evaluation.',
        dependencies=(),
    ),
    'nutation': ModuleContract(
        name='nutation',
        responsibility='IAU 2000A nutation calculations.',
        dependencies=(),
    ),
    'obliquity': ModuleContract(
        name='obliquity',
        responsibility='IAU 2006 mean and true obliquity.',
        dependencies=('nutation',),
    ),
    'solar_position': ModuleContract(
        name='solar_position',
        responsibility='Solar longitude, equation of time, and true solar time.',
        dependencies=('vsop87d', 'nutation', 'obliquity'),
    ),
    'root_finding': ModuleContract(
        name='root_finding',
        responsibility='Pure-Python bracketing and Brent solver.',
        dependencies=(),
    ),
    'solar_term_solver': ModuleContract(
        name='solar_term_solver',
        responsibility='Solar-term boundary solving.',
        dependencies=('solar_position', 'root_finding'),
    ),
    'sexagenary': ModuleContract(
        name='sexagenary',
        responsibility='Year, month, day, and hour pillar arithmetic.',
        dependencies=('conventions',),
    ),
    'output': ModuleContract(
        name='output',
        responsibility='Deterministic output serialization.',
        dependencies=(),
    ),
    'engine': ModuleContract(
        name='engine',
        responsibility='Main orchestration of full pipeline.',
        dependencies=(
            'conventions',
            'policy',
            'time_convert',
            'solar_position',
            'solar_term_solver',
            'sexagenary',
            'output',
        ),
    ),
    'geocoding': ModuleContract(
        name='geocoding',
        responsibility='City lookup to coordinates outside core engine calculations.',
        dependencies=(),
    ),
}


def _visit_for_cycle_check(
    module_name: str,
    visiting: set[str],
    visited: set[str],
    contracts: dict[str, ModuleContract],
) -> None:
    if module_name in visiting:
        raise ValueError(f'Circular dependency detected at module: {module_name}')
    if module_name in visited:
        return
    if module_name not in contracts:
        raise ValueError(f'Unknown module in dependency graph: {module_name}')

    visiting.add(module_name)
    for dependency in contracts[module_name].dependencies:
        _visit_for_cycle_check(dependency, visiting, visited, contracts)
    visiting.remove(module_name)
    visited.add(module_name)


def validate_module_contracts(
    contracts: dict[str, ModuleContract] | None = None,
) -> None:
    graph = contracts or MODULE_CONTRACTS

    for module_name, contract in graph.items():
        if contract.name != module_name:
            raise ValueError(f'Module key/name mismatch: {module_name} != {contract.name}')
        for dependency in contract.dependencies:
            if dependency not in graph:
                raise ValueError(
                    f'Module {module_name} references unknown dependency: {dependency}'
                )

    visiting: set[str] = set()
    visited: set[str] = set()
    for module_name in graph.keys():
        _visit_for_cycle_check(module_name, visiting, visited, graph)


def get_contract(module_name: str) -> ModuleContract:
    if module_name not in MODULE_CONTRACTS:
        raise KeyError(f'Unknown module contract: {module_name}')
    return MODULE_CONTRACTS[module_name]
