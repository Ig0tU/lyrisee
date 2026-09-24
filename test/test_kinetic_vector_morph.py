import unittest
import sys
import os

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from kinetic_vector_morph_prototype import (
    BezierPoint,
    BezierPath,
    DifferentiableMorphEngine,
    TransientStressKineticMapper,
    KineticVectorPipeline,
    demo_138bpm_verse
)


class TestKineticVectorMorph(unittest.TestCase):

    def test_bezier_point_lerp_and_shear(self):
        p1 = BezierPoint(0, 0)
        p2 = BezierPoint(10, 20)

        mid = p1.lerp(p2, 0.5)
        self.assertEqual(mid.to_tuple(), (5.0, 10.0))

        sheared = p1.apply_transient_shear(45.0, 10.0)
        self.assertAlmostEqual(sheared.x, 7.07, places=1)
        self.assertAlmostEqual(sheared.y, 7.07, places=1)

    def test_bezier_path_from_svg_and_resample(self):
        svg_d = "M 10 10 H 90 V 90 Z"
        path = BezierPath.from_svg_path(svg_d)
        self.assertTrue(path.closed)
        self.assertGreaterEqual(len(path.points), 3)

        resampled = path.resample(16)
        self.assertEqual(len(resampled.points), 16)
        self.assertTrue(resampled.to_svg_path().startswith("M "))

    def test_differentiable_morph_engine(self):
        engine = DifferentiableMorphEngine(readability_weight=0.3)
        src = BezierPath.from_svg_path("M 0 0 H 100 V 100 Z")
        tgt = BezierPath.from_svg_path("M 50 0 L 100 100 L 0 100 Z")

        chamfer = engine.chamfer_loss(src, tgt)
        self.assertGreater(chamfer, 0.0)

        morphed_t0 = engine.morph_step(src, tgt, t=0.0)
        morphed_t1 = engine.morph_step(src, tgt, t=1.0)
        self.assertEqual(len(morphed_t0.points), len(morphed_t1.points))

    def test_transient_stress_mapper(self):
        mapper = TransientStressKineticMapper(bpm=138.0)

        phonetics = mapper.analyze_phonemes("PISTON")
        self.assertTrue(phonetics["has_plosive"])
        self.assertTrue(phonetics["has_sibilant"])

        path = BezierPath.from_svg_path("M 10 10 H 50 V 50 Z")
        deformed = mapper.apply_transient_deformation(path, "PISTON")
        self.assertEqual(len(deformed.points), len(path.points))

    def test_kinetic_vector_pipeline_and_verse_demo(self):
        pipeline = KineticVectorPipeline(bpm=138.0)
        res = pipeline.process_lyric_event("GUILLOTINE", start_time=2.0, duration=0.8, metaphor_icon="guillotine")

        self.assertEqual(res["word"], "GUILLOTINE")
        self.assertEqual(len(res["keyframes"]), 5)
        self.assertIn("svg_path", res["keyframes"][0])

        demo_res = demo_138bpm_verse()
        self.assertEqual(len(demo_res), 6)


if __name__ == "__main__":
    unittest.main()
