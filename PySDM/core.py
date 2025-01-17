"""
Created at 09.11.2019
"""

import numpy as np

from PySDM.state.particles import Particles
from PySDM.storages.index import make_Index
from PySDM.storages.pair_indicator import make_PairIndicator
from PySDM.storages.pairwise_storage import make_PairwiseStorage
from PySDM.storages.indexed_storage import make_IndexedStorage


class Core:

    def __init__(self, n_sd, backend):
        assert isinstance(backend, object)
        self.__n_sd = n_sd

        self.backend = backend
        self.environment = None
        self.particles: (Particles, None) = None
        self.dynamics = {}
        self.products = {}
        self.observers = []

        self.n_steps = 0

        self.sorting_scheme = 'default'
        self.condensation_solver = None

        self.Index = make_Index(backend)
        self.PairIndicator = make_PairIndicator(backend)
        self.PairwiseStorage = make_PairwiseStorage(backend)
        self.IndexedStorage = make_IndexedStorage(backend)

        self.timers = {}

    @property
    def env(self):
        return self.environment

    @property
    def bck(self):
        return self.backend

    @property
    def Storage(self):
        return self.backend.Storage

    @property
    def Random(self):
        return self.backend.Random

    @property
    def n_sd(self) -> int:
        return self.__n_sd

    @property
    def dt(self) -> float:
        if self.environment is not None:
            return self.environment.dt

    @property
    def mesh(self):
        if self.environment is not None:
            return self.environment.mesh

    def normalize(self, prob, norm_factor):
        self.backend.normalize(
            prob, self.particles['cell id'], self.particles.cell_idx,
            self.particles.cell_start, norm_factor, self.dt, self.mesh.dv)

    def update_TpRH(self):
        self.backend.temperature_pressure_RH(
            # input
            self.env.get_predicted('rhod'),
            self.env.get_predicted('thd'),
            self.env.get_predicted('qv'),
            # output
            self.env.get_predicted('T'),
            self.env.get_predicted('p'),
            self.env.get_predicted('RH')
        )
        # TODO #443: mark_updated

    def condensation(self, kappa, rtol_x, rtol_thd, counters, RH_max, cell_order):
        particle_temperatures = \
            self.particles["temperature"] if self.particles.has_attribute("temperature") else \
            self.Storage.empty(0, dtype=float)

        self.backend.condensation(
                solver=self.condensation_solver,
                n_cell=self.mesh.n_cell,
                cell_start_arg=self.particles.cell_start,
                v=self.particles["volume"],
                particle_temperatures=particle_temperatures,
                n=self.particles['n'],
                vdry=self.particles["dry volume"],
                idx=self.particles._Particles__idx,
                rhod=self.env["rhod"],
                thd=self.env["thd"],
                qv=self.env["qv"],
                dv=self.env.dv,
                prhod=self.env.get_predicted("rhod"),
                pthd=self.env.get_predicted("thd"),
                pqv=self.env.get_predicted("qv"),
                kappa=kappa,
                rtol_x=rtol_x,
                rtol_thd=rtol_thd,
                v_cr=self.particles["critical volume"],
                dt=self.dt,
                counters=counters,
                cell_order=cell_order,
                RH_max=RH_max
            )

    def run(self, steps):
        for _ in range(steps):
            for key, dynamic in self.dynamics.items():
                with self.timers[key]:
                    dynamic()
            self.n_steps += 1
            reversed_order_so_that_environment_is_last = reversed(self.observers)
            for observer in reversed_order_so_that_environment_is_last:
                observer.notify()
