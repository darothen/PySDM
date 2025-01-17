from chempy import Substance

from PySDM.physics.formulae import vant_hoff, tdep2enthalpy, arrhenius
from PySDM.physics import si
from PySDM.physics.constants import R_str, ROOM_TEMP, H_u, dT_u, M, Md, K_H2O
import numpy as np


class EqConst:
    def __init__(self, constant_at_T0, dT, T_0):
        self.K = constant_at_T0
        self.dH = tdep2enthalpy(dT)
        self.T0 = T_0

    def at(self, T):
        return vant_hoff(self.K, self.dH, T, T_0=self.T0)


class KinConst:
    def __init__(self, k, dT, T_0):
        self.Ea = tdep2enthalpy(dT)
        self.A = k * np.exp(self.Ea / (R_str * T_0))

    def at(self, T):
        return arrhenius(self.A, self.Ea, T)


# TODO #442: unit tests against chempy
HENRY_CONST = {
    "HNO3": EqConst(2.1e5 * H_u, 0 * dT_u, T_0=ROOM_TEMP),
    "H2O2": EqConst(7.45e4 * H_u, 7300 * dT_u, T_0=ROOM_TEMP),
    "NH3":  EqConst(62 * H_u, 4110 * dT_u, T_0=ROOM_TEMP),
    "SO2":  EqConst(1.23 * H_u, 3150 * dT_u, T_0=ROOM_TEMP),
    "CO2":  EqConst(3.4e-2 * H_u, 2440 * dT_u, T_0=ROOM_TEMP),
    "O3":   EqConst(1.13e-2 * H_u, 2540 * dT_u, T_0=ROOM_TEMP),
}

# Table 4 in Kreidenweis et al. 2003
EQUILIBRIUM_CONST = {  # Reaction Specific units, K
    "K_HNO3": EqConst(15.4 * M, 0 * dT_u, T_0=ROOM_TEMP),
    "K_SO2":  EqConst(1.3e-2 * M, 1960 * dT_u, T_0=ROOM_TEMP),
    "K_NH3":  EqConst(1.7e-5 * M, -450 * dT_u, T_0=ROOM_TEMP),
    "K_CO2":  EqConst(4.3e-7 * M, -1000 * dT_u, T_0=ROOM_TEMP),
    "K_HSO3": EqConst(6.6e-8 * M, 1500 * dT_u, T_0=ROOM_TEMP),
    "K_HCO3": EqConst(4.68e-11 * M, -1760 * dT_u, T_0=ROOM_TEMP),
    "K_HSO4": EqConst(1.2e-2 * M, 2720 * dT_u, T_0=ROOM_TEMP),
}

DIFFUSION_CONST = {
    "HNO3": 65.25e-6 * si.m**2 / si.s,
    "H2O2": 87.00e-6 * si.m**2 / si.s,
    "NH3":  19.78e-6 * si.m**2 / si.s,
    "SO2":  10.89e-6 * si.m**2 / si.s,
    "CO2":  13.81e-6 * si.m**2 / si.s,
    "O3":   14.44e-6 * si.m**2 / si.s,
}

MASS_ACCOMMODATION_COEFFICIENTS = {
    "HNO3": 0.05,
    "H2O2": 0.018,
    "NH3":  0.05,
    "SO2":  0.035,
    "CO2":  0.05,
    "O3":   0.00053
}

AQUEOUS_COMPOUNDS = {
    "S_IV": ("SO2 H2O", "HSO3", "SO3"),  # rename: SO2 H2O -> H2SO3(aq) ?
    "O3": ("O3",),
    "H2O2": ("H2O2",),
    "C_IV": ("CO2 H2O", "HCO3", "CO3"),  # ditto
    "N_V": ("HNO3", "NO3"),
    "N_mIII": ("NH4", "H2O NH3"),
    "S_VI": ("SO4", "HSO4"),
}

GASEOUS_COMPOUNDS = {
    "N_V": "HNO3",
    "H2O2": "H2O2",
    "N_mIII": "NH3",
    "S_IV": "SO2",
    "C_IV": "CO2",
    "O3": "O3"
}

DISSOCIATION_FACTORS = {
    "CO2": lambda H, eqc, cell_id: 1 + eqc["K_CO2"].data[cell_id] * (1 / H + eqc["K_HCO3"].data[cell_id] / (H ** 2)),
    "SO2": lambda H, eqc, cell_id: 1 + eqc["K_SO2"].data[cell_id] * (1 / H + eqc["K_HSO3"].data[cell_id] / (H ** 2)),
    "NH3": lambda H, eqc, cell_id: 1 + eqc["K_NH3"].data[cell_id] / K_H2O * H,
    "HNO3": lambda H, eqc, cell_id: 1 + eqc["K_HNO3"].data[cell_id] / H,
    "O3": lambda _, __, ___: 1,
    "H2O2": lambda _, __, ___: 1
}

KINETIC_CONST = {
    "k0": KinConst(k=2.4e4 / si.s / M, dT=0 * dT_u, T_0=ROOM_TEMP),
    "k1": KinConst(k=3.5e5 / si.s / M, dT=-5530 * dT_u, T_0=ROOM_TEMP),
    "k2": KinConst(k=1.5e9 / si.s / M, dT=-5280 * dT_u, T_0=ROOM_TEMP),
    # Different unit due to a different pseudo-order of kinetics
    "k3": KinConst(k=7.45e9 / si.s / M / M, dT=-4430 * dT_u, T_0=ROOM_TEMP),
}

SPECIFIC_GRAVITY = {
    compound: Substance.from_formula(compound).mass * si.gram / si.mole / Md
    for compound in {*GASEOUS_COMPOUNDS.values()}
}

for compounds in AQUEOUS_COMPOUNDS.values():
    for compound in compounds:
        SPECIFIC_GRAVITY[compound] = Substance.from_formula(compound).mass * si.gram / si.mole / Md