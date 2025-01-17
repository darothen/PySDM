"""
Created at 25.11.2019
"""

import numpy as np
from PySDM.initialisation.r_wet_init import r_wet_init, default_rtol
from PySDM.initialisation.multiplicities import discretise_n
from PySDM.physics import formulae as phys
from ..physics import constants as const
from ._moist import _Moist
from PySDM.state.mesh import Mesh


class Parcel(_Moist):

    def __init__(
            self, dt,
            mass_of_dry_air: float,
            p0: float, q0: float, T0: float,
            w: [float, callable],
            z0: float = 0,
            g=const.g_std
    ):

        super().__init__(dt, Mesh.mesh_0d(), ['rhod', 'z', 't'])

        self.w = w if callable(w) else lambda _: w
        self.g = g

        pd0 = phys.MoistAir.p_d(p0, q0)
        rhod0 = phys.MoistAir.rhod_of_pd_T(pd0, T0)

        self.params = (q0, phys.th_std(pd0, T0), rhod0, z0, 0)
        self.mesh.dv = phys.Trivia.volume_of_density_mass(rhod0, mass_of_dry_air)

        self.mass_of_dry_air = mass_of_dry_air
        self.dql = None

    @property
    def dv(self):
        rhod_mean = (self.get_predicted("rhod")[0] + self["rhod"][0]) / 2
        return phys.Trivia.volume_of_density_mass(rhod_mean, self.mass_of_dry_air)

    def register(self, builder):
        _Moist.register(self, builder)
        self['qv'][:] = self.params[0]
        self['thd'][:] = self.params[1]
        self['rhod'][:] = self.params[2]
        self['z'][:] = self.params[3]
        self['t'][:] = self.params[4]
        delattr(self, 'params')

        self.sync_parcel_vars()
        _Moist.sync(self)
        self.notify()

    def init_attributes(self, *, n_in_dv: [float, np.ndarray], kappa: float, r_dry: [float, np.ndarray],
                        rtol=default_rtol):
        if not isinstance(n_in_dv, np.ndarray):
            r_dry = np.array([r_dry])
            n_in_dv = np.array([n_in_dv])

        attributes = {}
        attributes['dry volume'] = phys.volume(radius=r_dry)
        attributes['n'] = discretise_n(n_in_dv)
        r_wet = r_wet_init(r_dry, self, np.zeros_like(attributes['n']), kappa, rtol)
        attributes['volume'] = phys.volume(radius=r_wet)
        return attributes

    def advance_parcel_vars(self):
        dt = self.core.dt
        T = self['T'][0]
        p = self['p'][0]
        t = self['t'][0]

        dz_dt = self.w(t + dt/2)  # "mid-point"
        qv = self['qv'][0] - self.dql/2

        dql_dz = self.dql / dz_dt / dt
        drho_dz = phys.Hydrostatic.drho_dz(self.g, p, T, qv, dql_dz=dql_dz)
        drhod_dz = drho_dz

        phys.explicit_euler(self._tmp['t'][:], dt, 1)
        phys.explicit_euler(self._tmp['z'][:], dt, dz_dt)
        phys.explicit_euler(self._tmp['rhod'][:], dt, dz_dt * drhod_dz)

        self.mesh.dv = phys.Trivia.volume_of_density_mass(
            (self._tmp['rhod'][0] + self["rhod"][0]) / 2,
            self.mass_of_dry_air
        )

    def get_thd(self):
        return self['thd']

    def get_qv(self):
        return self['qv']

    def sync_parcel_vars(self):
        self.dql = self._tmp['qv'][0] - self['qv'][0]
        for var in self.variables:
            self._tmp[var][:] = self[var][:]

    def sync(self):
        self.sync_parcel_vars()
        self.advance_parcel_vars()
        super().sync()
