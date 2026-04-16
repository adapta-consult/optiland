"""Tests for chromatic aberration analysis classes."""

from __future__ import annotations

import pytest
import numpy as np
import matplotlib
matplotlib.use("Agg")

import optiland.backend as be
from optiland.analysis import ChromaticFocalShift, LateralColor
from optiland.samples import CementedAchromat, Edmund_49_847


def make_singlet():
    """Simple singlet with F/d/C wavelengths for chromatic tests."""
    from optiland import optic
    lens = optic.Optic()
    lens.surfaces.add(index=0, radius=be.inf, thickness=be.inf)
    lens.surfaces.add(index=1, thickness=5.0, radius=51.68, is_stop=True, material="N-BK7")
    lens.surfaces.add(index=2, thickness=93.0, radius=be.inf)
    lens.surfaces.add(index=3)
    lens.set_aperture(aperture_type="EPD", value=25.0)
    lens.fields.set_type("angle")
    lens.fields.add(y=0.0)
    lens.fields.add(y=3.0)
    lens.fields.add(y=5.0)
    lens.wavelengths.add(value=0.4861)   # F line
    lens.wavelengths.add(value=0.5876, is_primary=True)  # d line
    lens.wavelengths.add(value=0.6563)   # C line
    return lens


def make_singlet_one_field():
    """Singlet with on-axis field only."""
    from optiland import optic
    lens = optic.Optic()
    lens.surfaces.add(index=0, radius=be.inf, thickness=be.inf)
    lens.surfaces.add(index=1, thickness=5.0, radius=51.68, is_stop=True, material="N-BK7")
    lens.surfaces.add(index=2, thickness=93.0, radius=be.inf)
    lens.surfaces.add(index=3)
    lens.set_aperture(aperture_type="EPD", value=25.0)
    lens.fields.set_type("angle")
    lens.fields.add(y=0.0)
    lens.wavelengths.add(value=0.4861)
    lens.wavelengths.add(value=0.5876, is_primary=True)
    lens.wavelengths.add(value=0.6563)
    return lens


def make_single_wavelength_system():
    """Lens with only one wavelength — should raise ValueError."""
    from optiland import optic
    lens = optic.Optic()
    lens.surfaces.add(index=0, radius=be.inf, thickness=be.inf)
    lens.surfaces.add(index=1, thickness=5.0, radius=51.68, is_stop=True, material="N-BK7")
    lens.surfaces.add(index=2, thickness=93.0, radius=be.inf)
    lens.surfaces.add(index=3)
    lens.set_aperture(aperture_type="EPD", value=25.0)
    lens.fields.set_type("angle")
    lens.fields.add(y=0.0)
    lens.wavelengths.add(value=0.5876, is_primary=True)
    return lens


# ---------------------------------------------------------------------------
# ChromaticFocalShift tests
# ---------------------------------------------------------------------------

class TestChromaticFocalShift:
    def test_singlet_has_significant_chromatic_shift(self):
        lens = make_singlet()
        cfs = ChromaticFocalShift(lens)
        max_shift = float(be.to_numpy(cfs.max_shift))
        assert max_shift > 0.5, f"Expected singlet max shift > 0.5 mm, got {max_shift}"

    def test_achromat_has_reduced_chromatic_shift(self):
        singlet = make_singlet()
        achromat = CementedAchromat()

        cfs_singlet = ChromaticFocalShift(singlet)
        cfs_achromat = ChromaticFocalShift(achromat)

        singlet_shift = float(be.to_numpy(cfs_singlet.max_shift))
        achromat_shift = float(be.to_numpy(cfs_achromat.max_shift))
        assert achromat_shift * 10 < singlet_shift, (
            f"Achromat shift ({achromat_shift:.4f}) should be at least 10x less "
            f"than singlet ({singlet_shift:.4f})"
        )

    def test_positive_focal_length_for_converging_lens(self):
        achromat = CementedAchromat()
        cfs = ChromaticFocalShift(achromat)
        fl_np = be.to_numpy(cfs.focal_lengths)
        assert np.all(fl_np > 0), f"All focal lengths should be positive, got {fl_np}"

    def test_wavelengths_sorted_ascending(self):
        lens = make_singlet()
        cfs = ChromaticFocalShift(lens)
        wl_values = [wp.value for wp in cfs.wavelengths]
        assert wl_values == sorted(wl_values), "Wavelengths must be sorted ascending"

    def test_primary_focal_shift_is_zero(self):
        lens = make_singlet()
        cfs = ChromaticFocalShift(lens)
        primary_idx = min(
            range(len(cfs.wavelengths)),
            key=lambda i: abs(cfs.wavelengths[i].value - cfs.primary_wavelength),
        )
        shift_at_primary = float(be.to_numpy(cfs.focal_shifts[primary_idx]))
        assert abs(shift_at_primary) < 1e-9, (
            f"Focal shift at primary wavelength must be 0, got {shift_at_primary}"
        )

    def test_num_wavelengths_adds_samples(self):
        lens = make_singlet()
        cfs = ChromaticFocalShift(lens, num_wavelengths=11)
        assert len(cfs.wavelengths) >= 11, (
            f"Expected >= 11 wavelengths, got {len(cfs.wavelengths)}"
        )

    def test_num_wavelengths_preserves_native_wavelengths(self):
        lens = make_singlet()
        native = [w.value for w in lens.wavelengths.wavelengths]
        cfs = ChromaticFocalShift(lens, num_wavelengths=7)
        wl_values = [wp.value for wp in cfs.wavelengths]
        for n in native:
            assert any(abs(w - n) < 1e-8 for w in wl_values), (
                f"Native wavelength {n} not preserved in output"
            )

    def test_view_returns_figure_and_axes(self):
        import matplotlib.pyplot as plt
        from matplotlib.figure import Figure
        from matplotlib.axes import Axes
        lens = make_singlet()
        cfs = ChromaticFocalShift(lens)
        fig, ax = cfs.view()
        assert isinstance(fig, Figure)
        assert isinstance(ax, Axes)
        plt.close(fig)

    def test_single_wavelength_raises(self):
        lens = make_single_wavelength_system()
        with pytest.raises(ValueError):
            ChromaticFocalShift(lens)

    def test_data_length_matches_wavelengths(self):
        lens = make_singlet()
        cfs = ChromaticFocalShift(lens)
        assert len(cfs.data) == len(cfs.wavelengths)

    def test_convenience_attributes_set(self):
        lens = make_singlet()
        cfs = ChromaticFocalShift(lens)
        assert hasattr(cfs, "focal_lengths")
        assert hasattr(cfs, "focal_shifts")
        assert hasattr(cfs, "normalized_focal_shifts")
        assert hasattr(cfs, "primary_focal_length")
        assert hasattr(cfs, "primary_wavelength")
        assert hasattr(cfs, "max_shift")


# ---------------------------------------------------------------------------
# LateralColor tests
# ---------------------------------------------------------------------------

class TestLateralColor:
    def test_on_axis_lateral_color_is_zero(self):
        lens = make_singlet()
        lc = LateralColor(lens)
        wl_values = [wp.value for wp in lc.wavelengths]
        fields_np = be.to_numpy(lc.fields)
        lc_np = be.to_numpy(lc.lateral_color)

        # Find on-axis field index
        on_axis_idx = int(np.argmin(np.abs(fields_np)))
        on_axis_lc = lc_np[on_axis_idx, :]
        assert np.all(np.abs(on_axis_lc) < 1e-6), (
            f"On-axis lateral color must be < 1e-6 mm for all wavelengths, "
            f"got {on_axis_lc}"
        )

    def test_wavelengths_sorted_ascending(self):
        lens = make_singlet()
        lc = LateralColor(lens)
        wl_values = [wp.value for wp in lc.wavelengths]
        assert wl_values == sorted(wl_values), "Wavelengths must be sorted ascending"

    def test_valid_mask_all_true_for_good_lens(self):
        lens = make_singlet()
        lc = LateralColor(lens)
        valid_np = be.to_numpy(lc.valid_mask)
        assert np.all(valid_np), "All rays should be valid for a well-behaved singlet"

    def test_view_returns_figure_and_axes(self):
        import matplotlib.pyplot as plt
        from matplotlib.figure import Figure
        from matplotlib.axes import Axes
        lens = make_singlet()
        lc = LateralColor(lens)
        fig, ax = lc.view()
        assert isinstance(fig, Figure)
        assert isinstance(ax, Axes)
        plt.close(fig)

    def test_single_wavelength_raises(self):
        lens = make_single_wavelength_system()
        with pytest.raises(ValueError):
            LateralColor(lens)

    def test_data_length_matches_wavelengths(self):
        lens = make_singlet()
        lc = LateralColor(lens)
        assert len(lc.data) == len(lc.wavelengths)

    def test_image_heights_shape(self):
        lens = make_singlet()
        lc = LateralColor(lens)
        h_np = be.to_numpy(lc.image_heights)
        num_fields = len(lens.fields.get_field_coords())
        num_wl = len(lc.wavelengths)
        assert h_np.shape == (num_fields, num_wl), (
            f"Expected shape ({num_fields}, {num_wl}), got {h_np.shape}"
        )

    def test_lateral_color_shape(self):
        lens = make_singlet()
        lc = LateralColor(lens)
        lc_np = be.to_numpy(lc.lateral_color)
        num_fields = len(lens.fields.get_field_coords())
        num_wl = len(lc.wavelengths)
        assert lc_np.shape == (num_fields, num_wl)

    def test_primary_lateral_color_is_zero(self):
        lens = make_singlet()
        lc = LateralColor(lens)
        primary_idx = min(
            range(len(lc.wavelengths)),
            key=lambda i: abs(lc.wavelengths[i].value - lc.primary_wavelength),
        )
        lc_np = be.to_numpy(lc.lateral_color)
        assert np.all(np.abs(lc_np[:, primary_idx]) < 1e-9), (
            "Lateral color at primary wavelength must be 0 for all fields"
        )

    def test_num_wavelengths_adds_samples(self):
        lens = make_singlet()
        lc = LateralColor(lens, num_wavelengths=9)
        assert len(lc.wavelengths) >= 9

    def test_achromat_has_less_lateral_color_than_singlet(self):
        singlet = make_singlet()
        achromat = CementedAchromat()

        lc_singlet = LateralColor(singlet)
        lc_achromat = LateralColor(achromat)

        max_singlet = float(be.to_numpy(lc_singlet.max_lateral_color))
        max_achromat = float(be.to_numpy(lc_achromat.max_lateral_color))
        # Achromat should have substantially less lateral color
        assert max_achromat <= max_singlet, (
            f"Achromat lateral color ({max_achromat:.6f}) should be <= "
            f"singlet ({max_singlet:.6f})"
        )
