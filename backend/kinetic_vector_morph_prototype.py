"""
Kinetic Vector Morph Prototype - Multi-Stage Differentiable Vector Typographic Deformation
Part of Lyrisee AI Kinetic Typography Engine.

Implements vector glyph deformation, Bézier path morphing, transient-locked coordinate snapping,
and semantic-to-icon vector extrapolation for high-bpm multi-layered lyric streams.
"""

import math
import re
import json
from typing import List, Dict, Tuple, Optional


class BezierPoint:
    """Represents a 2D point or control point in a Bézier vector path."""
    def __init__(self, x: float, y: float, pt_type: str = 'anchor'):
        self.x = float(x)
        self.y = float(y)
        self.pt_type = pt_type  # 'anchor', 'control_in', 'control_out'

    def lerp(self, target: 'BezierPoint', t: float) -> 'BezierPoint':
        """Linear interpolation between points."""
        return BezierPoint(
            self.x + (target.x - self.x) * t,
            self.y + (target.y - self.y) * t,
            self.pt_type
        )

    def apply_transient_shear(self, angle_deg: float, magnitude: float) -> 'BezierPoint':
        """Apply directional shear vector for sibilant/plosive transients."""
        rad = math.radians(angle_deg)
        new_x = self.x + math.cos(rad) * magnitude
        new_y = self.y + math.sin(rad) * magnitude
        return BezierPoint(new_x, new_y, self.pt_type)

    def to_tuple(self) -> Tuple[float, float]:
        return (round(self.x, 2), round(self.y, 2))


class BezierPath:
    """Represents a vector path constructed from cubic/quadratic/linear SVG segments."""
    def __init__(self, points: Optional[List[BezierPoint]] = None, closed: bool = False):
        self.points = points or []
        self.closed = closed

    @classmethod
    def from_svg_path(cls, path_str: str) -> 'BezierPath':
        """Parse simple SVG path string into normalized BezierPoint sequence."""
        tokens = re.findall(r'[MLHVQCZz]|-?\d+(?:\.\d+)?', path_str)
        pts = []
        i = 0
        cmd = ''
        curr_x, curr_y = 0.0, 0.0
        closed = False

        while i < len(tokens):
            tok = tokens[i]
            if re.match(r'^[MLHVQCZz]$', tok):
                cmd = tok
                i += 1
                if cmd in ('Z', 'z'):
                    closed = True
                continue

            if cmd in ('M', 'L'):
                curr_x, curr_y = float(tokens[i]), float(tokens[i+1])
                pts.append(BezierPoint(curr_x, curr_y, 'anchor'))
                i += 2
            elif cmd == 'H':
                curr_x = float(tokens[i])
                pts.append(BezierPoint(curr_x, curr_y, 'anchor'))
                i += 1
            elif cmd == 'V':
                curr_y = float(tokens[i])
                pts.append(BezierPoint(curr_x, curr_y, 'anchor'))
                i += 1
            elif cmd == 'C':
                c1x, c1y = float(tokens[i]), float(tokens[i+1])
                c2x, c2y = float(tokens[i+2]), float(tokens[i+3])
                curr_x, curr_y = float(tokens[i+4]), float(tokens[i+5])
                pts.append(BezierPoint(c1x, c1y, 'control_in'))
                pts.append(BezierPoint(c2x, c2y, 'control_out'))
                pts.append(BezierPoint(curr_x, curr_y, 'anchor'))
                i += 6
            elif cmd == 'Q':
                cx, cy = float(tokens[i]), float(tokens[i+1])
                curr_x, curr_y = float(tokens[i+2]), float(tokens[i+3])
                pts.append(BezierPoint(cx, cy, 'control_in'))
                pts.append(BezierPoint(curr_x, curr_y, 'anchor'))
                i += 4
            else:
                i += 1

        return cls(points=pts, closed=closed)

    def resample(self, target_count: int) -> 'BezierPath':
        """Resample path to uniform point count for point-to-point morphing."""
        if not self.points:
            return BezierPath([BezierPoint(0, 0)] * target_count, self.closed)
        if len(self.points) == target_count:
            return BezierPath([BezierPoint(p.x, p.y, p.pt_type) for p in self.points], self.closed)

        resampled = []
        n = len(self.points)
        for i in range(target_count):
            pos = (i / max(1, target_count - 1)) * (n - 1)
            idx0 = int(math.floor(pos))
            idx1 = min(n - 1, idx0 + 1)
            frac = pos - idx0
            resampled.append(self.points[idx0].lerp(self.points[idx1], frac))

        return BezierPath(resampled, self.closed)

    def to_svg_path(self) -> str:
        """Convert points back into SVG path string."""
        if not self.points:
            return ""
        cmds = [f"M {self.points[0].x:.2f} {self.points[0].y:.2f}"]
        for p in self.points[1:]:
            cmds.append(f"L {p.x:.2f} {p.y:.2f}")
        if self.closed:
            cmds.append("Z")
        return " ".join(cmds)


class DifferentiableMorphEngine:
    """
    Simulates DiffVG / Bézier Splatting vector optimization.
    Applies gradient updates toward target scene icon geometry while enforcing
    a Readability Regularization Loss (CRNN/Chamfer distance proxy).
    """
    def __init__(self, readability_weight: float = 0.4):
        self.readability_weight = readability_weight

    def chamfer_loss(self, path_a: BezierPath, path_b: BezierPath) -> float:
        """Computes Chamfer Distance between point sets of two paths."""
        if not path_a.points or not path_b.points:
            return 0.0
        dist_sum = 0.0
        for pa in path_a.points:
            min_d = min((pa.x - pb.x)**2 + (pa.y - pb.y)**2 for pb in path_b.points)
            dist_sum += math.sqrt(min_d)
        return dist_sum / len(path_a.points)

    def morph_step(self, source_glyph: BezierPath, target_icon: BezierPath, t: float) -> BezierPath:
        """
        Morph source glyph vector towards target icon geometry at time step t [0, 1].
        Applies readability constraint to preserve glyph identity before morph point.
        """
        target_pts_count = max(len(source_glyph.points), len(target_icon.points), 16)
        src_resampled = source_glyph.resample(target_pts_count)
        tgt_resampled = target_icon.resample(target_pts_count)

        # Apply non-linear ease-in-out curve for structural morph
        smooth_t = (1 - math.cos(t * math.pi)) / 2

        # Readability factor retains source glyph shape longer
        effective_t = smooth_t * (1.0 - self.readability_weight * (1.0 - smooth_t))

        morphed_pts = []
        for p_src, p_tgt in zip(src_resampled.points, tgt_resampled.points):
            morphed_pts.append(p_src.lerp(p_tgt, effective_t))

        return BezierPath(morphed_pts, closed=source_glyph.closed or target_icon.closed)


class TransientStressKineticMapper:
    """
    Maps acoustic transients, sibilants, plosives, and rhythmic double-time pockets
    directly to vector coordinate transformations.
    """
    PLOSIVES = {'P', 'B', 'T', 'K', 'D', 'G'}
    SIBILANTS = {'S', 'Z', 'SH', 'ZH', 'F', 'V'}

    def __init__(self, bpm: float = 138.0):
        self.bpm = bpm
        self.beat_interval = 60.0 / bpm

    def analyze_phonemes(self, word: str) -> Dict[str, bool]:
        """Classifies phonetic stress characteristics for a word."""
        clean = word.upper().strip()
        has_plosive = any(p in clean for p in self.PLOSIVES)
        has_sibilant = any(s in clean for s in self.SIBILANTS)
        return {
            "has_plosive": has_plosive,
            "has_sibilant": has_sibilant,
            "is_double_time": len(clean) >= 6
        }

    def apply_transient_deformation(self, path: BezierPath, word: str, transient_power: float = 1.0) -> BezierPath:
        """
        Applies transient-locked snapping or directional shear vectors to Bézier paths.
        - Plosives: hard snap / scale spike
        - Sibilants: 45-degree directional vector shear
        """
        analysis = self.analyze_phonemes(word)
        new_pts = []

        for pt in path.points:
            p = BezierPoint(pt.x, pt.y, pt.pt_type)
            if analysis["has_plosive"]:
                # Hard plosive transient snap: outward radial displacement
                scale = 1.0 + (0.25 * transient_power)
                p.x *= scale
                p.y *= scale
            if analysis["has_sibilant"]:
                # Sibilant shear along line weight
                p = p.apply_transient_shear(angle_deg=45.0, magnitude=4.0 * transient_power)
            new_pts.append(p)

        return BezierPath(new_pts, closed=path.closed)


class KineticVectorPipeline:
    """
    Full 4-tier pipeline coordinator:
    Deconstruction -> Vector Glyph -> Morph Engine -> Kinetic Motion Output
    """
    def __init__(self, bpm: float = 138.0):
        self.bpm = bpm
        self.morph_engine = DifferentiableMorphEngine(readability_weight=0.35)
        self.transient_mapper = TransientStressKineticMapper(bpm=bpm)

    def generate_icon_vector(self, icon_name: str) -> BezierPath:
        """Generates target canonical vector geometries for semantic metaphors."""
        icon_name = icon_name.lower()
        if icon_name == 'piston':
            # Cylinder & steel shaft geometry
            return BezierPath.from_svg_path("M 40 20 H 160 V 180 H 40 Z M 80 180 V 220 H 120 V 180 Z")
        elif icon_name == 'guillotine':
            # Triangular blade & frame
            return BezierPath.from_svg_path("M 20 20 H 180 V 200 H 20 Z M 40 40 L 160 120 H 40 Z")
        elif icon_name == 'gear':
            # Cogwheel points
            return BezierPath.from_svg_path("M 100 30 L 120 50 L 150 40 L 160 70 L 190 90 L 170 120 L 180 150 L 150 160 Z")
        elif icon_name == 'casing':
            # Shell casing cylinder
            return BezierPath.from_svg_path("M 70 30 H 130 V 160 Q 130 180 100 180 Q 70 180 70 160 Z")
        else:
            # Default star/diamond
            return BezierPath.from_svg_path("M 100 20 L 130 80 L 190 100 L 130 120 L 100 180 L 70 120 L 10 100 L 70 80 Z")

    def process_lyric_event(
        self,
        word: str,
        start_time: float,
        duration: float,
        metaphor_icon: Optional[str] = None
    ) -> Dict:
        """
        Processes a single lyric word into timecoded morph frames and SVG path data.
        """
        # Standin glyph vector (box/letterform outline)
        glyph_path = BezierPath.from_svg_path("M 30 30 H 170 V 170 H 30 Z")

        # Transient deformation
        kinetic_glyph = self.transient_mapper.apply_transient_deformation(glyph_path, word, transient_power=0.8)

        frames = []
        steps = 5
        for s in range(steps):
            t = s / max(1, steps - 1)
            time_offset = start_time + (t * duration)

            if metaphor_icon:
                target_icon = self.generate_icon_vector(metaphor_icon)
                morphed = self.morph_engine.morph_step(kinetic_glyph, target_icon, t)
            else:
                morphed = kinetic_glyph

            frames.append({
                "time": round(time_offset, 3),
                "progress": round(t, 2),
                "svg_path": morphed.to_svg_path()
            })

        return {
            "word": word,
            "start_time": start_time,
            "duration": duration,
            "phonetics": self.transient_mapper.analyze_phonemes(word),
            "metaphor_target": metaphor_icon,
            "keyframes": frames
        }


def demo_138bpm_verse():
    """Executes the 138 BPM rap verse demo through the Kinetic Vector Pipeline."""
    pipeline = KineticVectorPipeline(bpm=138.0)
    verse_data = [
        {"word": "INK", "t": 0.0, "dur": 0.4, "metaphor": None},
        {"word": "PISTON", "t": 0.4, "dur": 0.6, "metaphor": "piston"},
        {"word": "FRICTION", "t": 1.0, "dur": 0.5, "metaphor": None},
        {"word": "SYNTAX", "t": 1.5, "dur": 0.4, "metaphor": None},
        {"word": "GUILLOTINE", "t": 2.2, "dur": 0.8, "metaphor": "guillotine"},
        {"word": "CASINGS", "t": 3.0, "dur": 0.6, "metaphor": "casing"}
    ]

    results = []
    for item in verse_data:
        res = pipeline.process_lyric_event(
            word=item["word"],
            start_time=item["t"],
            duration=item["dur"],
            metaphor_icon=item["metaphor"]
        )
        results.append(res)

    return results


if __name__ == "__main__":
    out = demo_138bpm_verse()
    print(f"Processed {len(out)} lyric vector morph sequences successfully.")
    print(json.dumps(out[1], indent=2))
