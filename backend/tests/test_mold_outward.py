import unittest
import os
import sys
import types


class _LayoutManager:
    def setLayout(self, _layout):
        pass


class _SlicerApp:
    def layoutManager(self):
        return _LayoutManager()


class _Signal:
    def connect(self, _callback):
        pass


class _QTimer:
    timeout = _Signal()

    def start(self, _interval):
        pass


sys.modules.setdefault("qt", types.SimpleNamespace(QTimer=_QTimer))
sys.modules.setdefault("vtk", types.SimpleNamespace())
sys.modules.setdefault(
    "slicer",
    types.SimpleNamespace(
        app=_SlicerApp(),
        vtkMRMLLayoutNode=types.SimpleNamespace(SlicerLayoutFourUpView=1),
    ),
)

sys.path.insert(0, os.path.dirname(__file__))
from slicer_watcher import _outward_direction_from_nearest_skin


class MoldOutwardDirectionTest(unittest.TestCase):
    def test_uses_skin_to_bolus_offset_not_smallest_bbox_axis(self):
        # A wide, thin bolus patch: bbox minimum is Z, but the local skin-to-bolus
        # displacement is along +Y. Open-top mold generation should follow the
        # local outward direction, not the largest projected face normal.
        bolus_coords = [
            (10, 20, 10),
            (10, 20, 60),
            (10, 80, 10),
            (10, 80, 60),
            (11, 20, 10),
            (11, 80, 60),
        ]
        nearest_skin_coords = [(z, y - 5, x) for z, y, x in bolus_coords]

        axis, sign, extents_mm, mean_offsets_mm = _outward_direction_from_nearest_skin(
            bolus_coords, nearest_skin_coords, (1.0, 1.0, 1.0)
        )

        self.assertEqual(axis, 1)  # numpy axis order: z=0, y=1, x=2
        self.assertEqual(sign, 1)
        self.assertLess(extents_mm[0], extents_mm[1])
        self.assertEqual(mean_offsets_mm, [0.0, 5.0, 0.0])


if __name__ == "__main__":
    unittest.main()
