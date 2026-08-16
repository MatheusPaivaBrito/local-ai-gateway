import pytest

from app.domains.usage.telemetry import NvidiaSample, integrate_power_joules


def sample(t: float, power: float) -> NvidiaSample:
    return NvidiaSample(t, 0, 0, 0, power)


def test_trapezoidal_energy_known_case() -> None:
    samples = [sample(0, 100), sample(1, 200), sample(2, 100)]
    assert integrate_power_joules(samples) == pytest.approx(300.0)
