"""
Created at 04.01.2021
"""

from PySDM.products.product import Product


class CollisionRate(Product):

    def __init__(self):
        super().__init__(
            name='collision_rate',
            description='Collision rate',
            range=(0, 1e10)
        )
        self.coalescence = None

    def register(self, builder):
        super().register(builder)
        self.coalescence = self.core.dynamics['Coalescence']

    def get(self):  # TODO #345 take into account NUMBER of substeps (?)
        self.download_to_buffer(self.coalescence.collision_rate)
        self.coalescence.collision_rate[:] = 0
        return self.buffer
