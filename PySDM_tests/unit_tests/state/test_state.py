"""
Created at 2019
"""

from PySDM.state.particles_factory import ParticlesFactory
from PySDM_tests.unit_tests.dummy_core import DummyCore
from PySDM_tests.unit_tests.dummy_environment import DummyEnvironment
from PySDM.backends import CPU as BACKEND

import numpy as np
import pytest


class TestParticles:

    @staticmethod
    def storage(iterable, idx=None):
        result = BACKEND.IndexedStorage.from_ndarray(np.array(iterable))
        if idx is not None:
            result = BACKEND.IndexedStorage.indexed(idx, result)
        return result

    @pytest.mark.parametrize("volume, n", [
        pytest.param(np.array([1., 1, 1, 1]), np.array([1, 1, 1, 1])),
        pytest.param(np.array([1., 2, 1, 1]), np.array([2, 0, 2, 0])),
        pytest.param(np.array([1., 1, 4]), np.array([5, 0, 0]))
    ])
    def test_housekeeping(self, volume, n):
        # Arrange
        core = DummyCore(BACKEND, n_sd=len(n))
        attributes = {'n': n, 'volume': volume}
        core.build(attributes)
        sut = core.particles
        sut.healthy = False

        # Act
        n_sd = sut.SD_num

        # Assert
        assert sut.SD_num == (n != 0).sum()
        assert sut['n'].to_ndarray().sum() == n.sum()
        assert (sut['volume'].to_ndarray() * sut['n'].to_ndarray()).sum() == (volume * n).sum()

    @staticmethod
    @pytest.fixture(params=[1, 2, 3, 4, 5, 8, 9, 16])
    def thread_number(request):
        return request.param

    @pytest.mark.parametrize('n, cells, n_sd, idx, new_idx, cell_start', [
        ([1, 1, 1], [2, 0, 1], 3, [2, 0, 1], [1, 2, 0], [0, 1, 2, 3]),
        ([0, 1, 0, 1, 1], [3, 4, 0, 1, 2], 3, [4, 1, 3, 2, 0], [3, 4, 1], [0, 0, 1, 2, 2, 3]),
        ([1, 2, 3, 4, 5, 6, 0], [2, 2, 2, 2, 1, 1, 1], 6, [0, 1, 2, 3, 4, 5, 6], [4, 5, 0, 1, 2, 3], [0, 0, 2, 6])
    ])
    def test_sort_by_cell_id(self, n, cells, n_sd, idx, new_idx, cell_start, thread_number):
        # Arrange
        core = DummyCore(BACKEND, n_sd=n_sd)
        core.build(attributes={'n': np.zeros(n_sd)})
        sut = core.particles
        sut._Particles__idx = TestParticles.storage(idx)
        sut.attributes['n'].data = TestParticles.storage(n, sut._Particles__idx)
        n_cell = max(cells) + 1
        sut.attributes['cell id'].data = TestParticles.storage(cells, sut._Particles__idx)
        idx_length = len(sut._Particles__idx)
        sut._Particles__cell_start = TestParticles.storage([0] * (n_cell + 1))
        sut._Particles__n_sd = core.n_sd
        sut.healthy = 0 not in n
        sut._Particles__cell_caretaker = BACKEND.make_cell_caretaker(sut._Particles__idx, sut._Particles__cell_start)

        # Act
        sut.sanitize()
        sut._Particles__sort_by_cell_id()

        # Assert
        np.testing.assert_array_equal(np.array(new_idx), sut._Particles__idx[:sut.SD_num].to_ndarray())
        np.testing.assert_array_equal(np.array(cell_start), sut._Particles__cell_start.to_ndarray())

    def test_recalculate_cell_id(self):
        # Arrange
        n = np.ones(1, dtype=np.int64)
        droplet_id = 0
        initial_position = BACKEND.from_ndarray(np.array([[0], [0]]))
        grid = (1, 1)
        core = DummyCore(BACKEND, n_sd=1)
        core.environment = DummyEnvironment(grid=grid)
        cell_id, cell_origin, position_in_cell = core.mesh.cellular_attributes(initial_position)
        cell_origin[0, droplet_id] = .1
        cell_origin[1, droplet_id] = .2
        cell_id[droplet_id] = -1
        attribute = {'n': n, 'cell id': cell_id, 'cell origin': cell_origin, 'position in cell': position_in_cell}
        core.build(attribute)
        sut = core.particles

        # Act
        sut.recalculate_cell_id()

        # Assert
        assert sut['cell id'][droplet_id] == 0

    def test_permutation_global(self):
        n_sd = 8
        u01 = [.1, .4, .2, .5, .9, .1, .6, .3]

        # Arrange
        core = DummyCore(BACKEND, n_sd=n_sd)
        sut = ParticlesFactory.empty_particles(core, n_sd)
        idx_length = len(sut._Particles__idx)
        sut._Particles__tmp_idx = TestParticles.storage([0] * idx_length)
        sut._Particles__sorted = True
        sut._Particles__n_sd = core.n_sd
        u01 = TestParticles.storage(u01)

        # Act
        sut.permutation(u01, local=False)

        # Assert
        expected = np.array([1, 3, 5, 7, 6, 0, 4, 2])
        np.testing.assert_array_equal(sut._Particles__idx, expected)
        assert not sut._Particles__sorted

    def test_permutation_local(self):
        n_sd = 8
        u01 = [.1, .4, .2, .5, .9, .1, .6, .3]
        cell_start = [0, 0, 2, 5, 7, n_sd]

        # Arrange
        core = DummyCore(BACKEND, n_sd=n_sd)
        sut = ParticlesFactory.empty_particles(core, n_sd)
        idx_length = len(sut._Particles__idx)
        sut._Particles__tmp_idx = TestParticles.storage([0] * idx_length)
        sut._Particles__cell_start = TestParticles.storage(cell_start)
        sut._Particles__sorted = True
        sut._Particles__n_sd = core.n_sd
        u01 = TestParticles.storage(u01)

        # Act
        sut.permutation(u01, local=True)

        # Assert
        expected = np.array([1, 0, 2, 3, 4, 5, 6, 7])
        np.testing.assert_array_equal(sut._Particles__idx, expected)
        assert sut._Particles__sorted

    def test_permutation_global_repeatable(self):
        n_sd = 800
        u01 = np.random.random(n_sd)

        # Arrange
        core = DummyCore(BACKEND, n_sd=n_sd)
        sut = ParticlesFactory.empty_particles(core, n_sd)
        idx_length = len(sut._Particles__idx)
        sut._Particles__tmp_idx = TestParticles.storage([0] * idx_length)
        sut._Particles__sorted = True
        sut._Particles__n_sd = core.n_sd
        u01 = TestParticles.storage(u01)

        # Act
        sut.permutation(u01, local=False)
        expected = sut._Particles__idx.to_ndarray()
        sut._Particles__sorted = True
        sut._Particles__idx = TestParticles.storage(range(n_sd))
        sut.permutation(u01, local=False)

        # Assert
        np.testing.assert_array_equal(sut._Particles__idx, expected)
        assert not sut._Particles__sorted

    def test_permutation_local_repeatable(self):
        n_sd = 800
        idx = range(n_sd)
        u01 = np.random.random(n_sd)
        cell_start = [0, 0, 20, 250, 700, n_sd]

        # Arrange
        core = DummyCore(BACKEND, n_sd=n_sd)
        core.build(attributes={'n': np.zeros(n_sd)})
        sut = core.particles
        sut._Particles__idx = TestParticles.storage(idx)
        idx_length = len(sut._Particles__idx)
        sut._Particles__tmp_idx = TestParticles.storage([0] * idx_length)
        cell_id = []
        for i in range(len(cell_start) - 1):
            cell_id = cell_id + [i] * cell_start[i + 1]
        sut.attributes['cell id'].data = TestParticles.storage(cell_id)
        sut._Particles__cell_start = TestParticles.storage(cell_start)
        sut._Particles__sorted = True
        sut._Particles__n_sd = core.n_sd
        u01 = TestParticles.storage(u01)

        # Act
        sut.permutation(u01, local=True)
        expected = sut._Particles__idx.to_ndarray()
        sut._Particles__idx = TestParticles.storage(idx)
        sut.permutation(u01, local=True)

        # Assert
        np.testing.assert_array_equal(sut._Particles__idx, expected)
        assert sut._Particles__sorted
        sut._Particles__sort_by_cell_id()
        np.testing.assert_array_equal(sut._Particles__idx[:50], expected[:50])
