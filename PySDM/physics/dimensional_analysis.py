"""
Crated at 2019
"""

from importlib import reload
from PySDM.physics import constants
from PySDM.physics import formulae
from PySDM.physics.impl import formula as backend_formulae, flag


class DimensionalAnalysis:

    def __enter__(*_):
        flag.DIMENSIONAL_ANALYSIS = True
        reload(constants)
        reload(backend_formulae)
        reload(formulae)

    def __exit__(*_):
        flag.DIMENSIONAL_ANALYSIS = False
        reload(constants)
        reload(backend_formulae)
        reload(formulae)
