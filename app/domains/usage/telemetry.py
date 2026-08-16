import asyncio
import statistics
import time
from dataclasses import asdict, dataclass

try:
    import pynvml
except ImportError:  # CPU-only test/import path.
    pynvml = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class NvidiaSample:
    timestamp_s: float
    utilization_pct: float
    memory_used_mb: float
    temperature_c: float
    power_w: float


class NvidiaDevice:
    def __init__(self, index: int) -> None:
        if pynvml is None:
            raise RuntimeError("nvidia-ml-py is not installed")
        pynvml.nvmlInit()
        self._index = index
        self._handle = pynvml.nvmlDeviceGetHandleByIndex(index)

    @property
    def index(self) -> int:
        return self._index

    def name(self) -> str:
        value = pynvml.nvmlDeviceGetName(self._handle)
        return value.decode() if isinstance(value, bytes) else str(value)

    def sample(self, timestamp_s: float) -> NvidiaSample:
        utilization = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
        memory = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
        temperature = pynvml.nvmlDeviceGetTemperature(
            self._handle,
            pynvml.NVML_TEMPERATURE_GPU,
        )
        power_w = pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000.0
        return NvidiaSample(
            timestamp_s=timestamp_s,
            utilization_pct=float(utilization.gpu),
            memory_used_mb=memory.used / (1024 * 1024),
            temperature_c=float(temperature),
            power_w=float(power_w),
        )

    def total_energy_joules(self) -> float | None:
        try:
            energy_mj = pynvml.nvmlDeviceGetTotalEnergyConsumption(self._handle)
        except pynvml.NVMLError:
            return None
        return float(energy_mj) / 1000.0

    def close(self) -> None:
        pynvml.nvmlShutdown()


def integrate_power_joules(samples: list[NvidiaSample]) -> float:
    if len(samples) < 2:
        return 0.0
    energy = 0.0
    for first, second in zip(samples, samples[1:], strict=False):
        delta_t = max(0.0, second.timestamp_s - first.timestamp_s)
        energy += ((first.power_w + second.power_w) / 2.0) * delta_t
    return energy


@dataclass(frozen=True, slots=True)
class TelemetryResult:
    gpu_name: str
    gpu_index: int
    utilization_avg_pct: float
    utilization_peak_pct: float
    memory_peak_mb: float
    temperature_avg_c: float
    temperature_peak_c: float
    power_avg_w: float
    power_peak_w: float
    energy_joules: float
    energy_wh: float
    energy_source: str
    joules_per_output_token: float | None
    output_tokens_per_wh: float | None
    output_tokens_per_second: float | None
    estimated_energy_cost: float | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class NvidiaRequestMonitor:
    def __init__(self, device: NvidiaDevice, sample_interval_ms: int) -> None:
        self.device = device
        self.interval_s = max(sample_interval_ms, 10) / 1000.0
        self.samples: list[NvidiaSample] = []
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._start_energy_j: float | None = None
        self._started_at = 0.0

    async def start(self) -> None:
        self._started_at = time.perf_counter()
        self._start_energy_j = self.device.total_energy_joules()
        self.samples.append(self.device.sample(self._started_at))
        self._running = True
        self._task = asyncio.create_task(self._sample_loop())

    async def _sample_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.interval_s)
            if self._running:
                self.samples.append(self.device.sample(time.perf_counter()))

    async def stop(
        self,
        *,
        output_tokens: int,
        electricity_price_per_kwh: float | None,
    ) -> TelemetryResult:
        self._running = False
        if self._task is not None:
            await self._task
        ended_at = time.perf_counter()
        self.samples.append(self.device.sample(ended_at))
        end_energy_j = self.device.total_energy_joules()

        if self._start_energy_j is not None and end_energy_j is not None:
            energy_j = max(0.0, end_energy_j - self._start_energy_j)
            energy_source = "nvml_total_energy"
        else:
            energy_j = integrate_power_joules(self.samples)
            energy_source = "power_integration"

        energy_wh = energy_j / 3600.0
        duration_s = max(ended_at - self._started_at, 1e-9)
        joules_per_token = energy_j / output_tokens if output_tokens > 0 else None
        tokens_per_wh = output_tokens / energy_wh if output_tokens > 0 and energy_wh > 0 else None
        tokens_per_second = output_tokens / duration_s if output_tokens > 0 else None
        cost = (
            (energy_wh / 1000.0) * electricity_price_per_kwh
            if electricity_price_per_kwh is not None
            else None
        )

        return TelemetryResult(
            gpu_name=self.device.name(),
            gpu_index=self.device.index,
            utilization_avg_pct=statistics.fmean(s.utilization_pct for s in self.samples),
            utilization_peak_pct=max(s.utilization_pct for s in self.samples),
            memory_peak_mb=max(s.memory_used_mb for s in self.samples),
            temperature_avg_c=statistics.fmean(s.temperature_c for s in self.samples),
            temperature_peak_c=max(s.temperature_c for s in self.samples),
            power_avg_w=statistics.fmean(s.power_w for s in self.samples),
            power_peak_w=max(s.power_w for s in self.samples),
            energy_joules=energy_j,
            energy_wh=energy_wh,
            energy_source=energy_source,
            joules_per_output_token=joules_per_token,
            output_tokens_per_wh=tokens_per_wh,
            output_tokens_per_second=tokens_per_second,
            estimated_energy_cost=cost,
        )


class TelemetryService:
    def __init__(self, *, enabled: bool, gpu_index: int, sample_interval_ms: int) -> None:
        self.enabled = enabled
        self.sample_interval_ms = sample_interval_ms
        self.device = NvidiaDevice(gpu_index) if enabled else None

    def new_monitor(self) -> NvidiaRequestMonitor | None:
        if self.device is None:
            return None
        return NvidiaRequestMonitor(self.device, self.sample_interval_ms)

    def close(self) -> None:
        if self.device is not None:
            self.device.close()
