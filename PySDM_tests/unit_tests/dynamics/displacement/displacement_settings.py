"""
Created at 29.04.2020
"""

from PySDM_tests.unit_tests.dummy_core import DummyCore
from PySDM.dynamics import Displacement
import numpy as np
from PySDM_tests.unit_tests.dummy_environment import DummyEnvironment


class DisplacementSettings:
    def __init__(self):
        self.n = np.ones(1, dtype=np.int64)
        self.volume = np.ones(1, dtype=np.float64)
        self.grid = (1, 1)
        self.courant_field_data = (np.array([[0, 0]]).T, np.array([[0, 0]]))
        self.positions = [[0], [0]]
        self.scheme = 'FTBS'
        self.sedimentation = False
        self.dt = None

    def get_displacement(self, backend):
        core = DummyCore(backend, n_sd=len(self.n))
        core.environment = DummyEnvironment(
            dt=self.dt,
            grid=self.grid,
            courant_field_data=self.courant_field_data)
        positions = np.array(self.positions)
        cell_id, cell_origin, position_in_cell = core.mesh.cellular_attributes(positions)
        attributes = {
            'n': self.n,
            'volume': self.volume,
            'cell id': cell_id,
            'cell origin': cell_origin,
            'position in cell': position_in_cell
        }
        core.build(attributes)
        sut = Displacement(courant_field=self.courant_field_data, scheme=self.scheme, enable_sedimentation=self.sedimentation)
        sut.register(core)

        return sut, core
