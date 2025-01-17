"""
Created at 05.02.2020
"""

from PySDM.physics import constants as const
from PySDM.products.product import MoistEnvironmentProduct


class WaterVapourMixingRatio(MoistEnvironmentProduct):

    def __init__(self):
        super().__init__(
            description="Water vapour mixing ratio",
            name="qv",
            unit="g/kg",
            range=(5, 7.5),
            scale="linear",
        )

    def get(self):
        super().get()
        const.convert_to(self.buffer, const.si.gram / const.si.kilogram)
        return self.buffer
