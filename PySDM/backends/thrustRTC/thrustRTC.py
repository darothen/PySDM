"""
Created at 01.08.2019
"""

import os
import warnings
from PySDM.backends.thrustRTC.impl._algorithmic_methods import AlgorithmicMethods
from PySDM.backends.thrustRTC.impl._pair_methods import PairMethods
from PySDM.backends.thrustRTC.impl._index_methods import IndexMethods
from PySDM.backends.thrustRTC.impl._physics_methods import PhysicsMethods
from PySDM.backends.thrustRTC.storage import Storage as ImportedStorage
from PySDM.backends.thrustRTC.random import Random as ImportedRandom


class ThrustRTC(
    AlgorithmicMethods,
    PairMethods,
    IndexMethods,
    PhysicsMethods,
):
    ENABLE = True
    Storage = ImportedStorage
    Random = ImportedRandom

    default_croupier = 'global'

    def __init__(self, formulae):
        self.formulae = formulae

    @staticmethod
    def sanity_check():
        if not ThrustRTC.ENABLE \
           and 'CI' not in os.environ:
            warnings.warn('CUDA is not available, using FakeThrustRTC!')
