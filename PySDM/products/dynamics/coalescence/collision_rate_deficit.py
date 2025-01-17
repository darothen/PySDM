"""
Created at 04.01.2021
"""

from PySDM.products.product import Product


class CollisionRateDeficit(Product):

    def __init__(self):
        super().__init__(
            name='collision_rate_deficit',
            description='Collision rate deficit',
            range=(0, 1e10)
        )
        self.coalescence = None

    def register(self, builder):
        super().register(builder)
        self.coalescence = self.core.dynamics['Coalescence']

    def get(self):  # TODO #345 take into account NUMBER of substeps (?)
        self.download_to_buffer(self.coalescence.collision_rate_deficit)
        self.coalescence.collision_rate_deficit[:] = 0
        return self.buffer
