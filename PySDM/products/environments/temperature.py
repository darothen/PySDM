"""
Created at 18.10.2020
"""

from PySDM.products.product import MoistEnvironmentProduct


class Temperature(MoistEnvironmentProduct):

    def __init__(self):
        super().__init__(
            description="Temperature",
            name="T",
            unit="K",
            range=(275, 305),
            scale="linear"
        )
