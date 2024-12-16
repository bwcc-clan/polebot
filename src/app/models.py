
from attrs import field, frozen, validators


@frozen(kw_only=True)
class MapGroupConfig:
    weight: int = field(validator=[validators.ge(0), validators.le(100)])
    repeat_factor: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    maps: list[str] = field(factory=list)


@frozen(kw_only=True)
class EnvironmentGroupConfig:
    repeat_factor: float = field(validator=[validators.ge(0.0), validators.le(1.0)])
    environments: list[str] = field(factory=list)

@frozen(kw_only=True)
class WeightingConfig:
    groups: dict[str, MapGroupConfig]
    environments: dict[str, EnvironmentGroupConfig]
