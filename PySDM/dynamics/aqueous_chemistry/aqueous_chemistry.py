import numpy as np
from .support import EQUILIBRIUM_CONST, DIFFUSION_CONST, AQUEOUS_COMPOUNDS, GASEOUS_COMPOUNDS, KINETIC_CONST, \
    SPECIFIC_GRAVITY, M
from PySDM.physics.formulae import mole_fraction_2_mixing_ratio, pH2H


default_H_max = pH2H(pH=-1.)
default_H_min = pH2H(pH=14.)
default_pH_rtol = 1e-6
default_ionic_strength_threshold = 0.02 * M


class AqueousChemistry:
    def __init__(self, environment_mole_fractions, system_type, n_substep,
                 ionic_strength_threshold=default_ionic_strength_threshold,
                 pH_H_min=default_H_min,
                 pH_H_max=default_H_max,
                 pH_rtol=default_pH_rtol):
        self.environment_mixing_ratios = {}
        for key, compound in GASEOUS_COMPOUNDS.items():
            shape = (1,)  # TODO #440
            self.environment_mixing_ratios[compound] = np.full(
                shape,
                mole_fraction_2_mixing_ratio(environment_mole_fractions[compound], SPECIFIC_GRAVITY[compound])
            )
        self.core = None

        assert system_type in ('open', 'closed')
        self.system_type = system_type
        assert isinstance(n_substep, int) and n_substep > 0
        self.n_substep = n_substep
        self.ionic_strength_threshold=ionic_strength_threshold
        self.pH_H_max = pH_H_max
        self.pH_H_min = pH_H_min
        self.pH_rtol = pH_rtol

        self.kinetic_consts = {}
        self.equilibrium_consts = {}
        self.dissociation_factors = {}
        self.do_chemistry_flag = None

    def register(self, builder):
        self.core = builder.core
        for key in AQUEOUS_COMPOUNDS.keys():
            builder.request_attribute("conc_" + key)

        for key in KINETIC_CONST.keys():
            self.kinetic_consts[key] = self.core.Storage.empty(self.core.mesh.n_cell, dtype=float)
        for key in EQUILIBRIUM_CONST.keys():
            self.equilibrium_consts[key] = self.core.Storage.empty(self.core.mesh.n_cell, dtype=float)
        for key in DIFFUSION_CONST.keys():
            self.dissociation_factors[key] = self.core.Storage.empty(self.core.n_sd, dtype=float)
        self.do_chemistry_flag = self.core.Storage.empty(self.core.n_sd, dtype=bool)

    def __call__(self):
        self.core.particles.chem_recalculate_cell_data(
            equilibrium_consts=self.equilibrium_consts,
            kinetic_consts=self.kinetic_consts
        )
        for _ in range(self.n_substep):
            self.core.particles.chem_recalculate_drop_data(
                equilibrium_consts=self.equilibrium_consts,
                dissociation_factors=self.dissociation_factors
            )
            self.core.particles.dissolution(
                gaseous_compounds=GASEOUS_COMPOUNDS,
                system_type=self.system_type,
                dissociation_factors=self.dissociation_factors,
                environment_mixing_ratios=self.environment_mixing_ratios,
                dt=self.core.dt / self.n_substep,
                do_chemistry_flag=self.do_chemistry_flag
            )
            self.core.particles.chem_recalculate_drop_data(
                equilibrium_consts=self.equilibrium_consts,
                dissociation_factors=self.dissociation_factors
            )
            self.core.particles.oxidation(
                kinetic_consts=self.kinetic_consts,
                equilibrium_consts=self.equilibrium_consts,
                dissociation_factors=self.dissociation_factors,
                do_chemistry_flag=self.do_chemistry_flag,
                dt=self.core.dt / self.n_substep
            )
