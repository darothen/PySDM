"""
Created at 22.11.2019
"""

from PySDM_examples.Arabas_et_al_2015.simulation import Simulation
from PySDM_examples.Arabas_et_al_2015.settings import Settings
from PySDM.physics import si
import numpy as np
from matplotlib import pyplot


class DummyStorage:
    def __init__(self):
        self.profiles = []

    def init(*_): pass

    def save(self, data: np.ndarray, step: int, name: str):
        if name == "qv_env":
            self.profiles.append({"qv_env": np.mean(data, axis=0)})


def test_spin_up(plot=False):
    # Arrange
    settings = Settings()
    settings.dt = .5 * si.second
    settings.simulation_time = 20 * settings.dt
    settings.output_interval = 1 * settings.dt

    storage = DummyStorage()
    simulation = Simulation(settings, storage)
    simulation.reinit()

    # Act
    simulation.run()

    # Plot
    if plot:
        levels = np.arange(settings.grid[1])
        for step, datum in enumerate(storage.profiles):
            pyplot.plot(datum["qv_env"], levels, label=str(step))
        pyplot.legend()
        pyplot.show()

    # Assert
    step_num = len(storage.profiles) - 1
    for step in range(step_num):
        next = storage.profiles[step + 1]["qv_env"]
        prev = storage.profiles[step]["qv_env"]
        eps = 1e-3
        assert ((prev + eps) >= next).all()
    assert storage.profiles[step_num]["qv_env"][-1] < 7.
