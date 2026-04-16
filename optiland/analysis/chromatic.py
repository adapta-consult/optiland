"""Chromatic Aberration Analysis

This module provides chromatic focal shift and lateral color analysis for
optical systems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np

import optiland.backend as be

from .base import BaseAnalysis

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


class ChromaticFocalShift(BaseAnalysis):
    """Paraxial longitudinal chromatic aberration: focal length vs. wavelength.

    Args:
        optic (Optic): The optic object to analyze.
        wavelengths (str or list, optional): Wavelengths to analyze.
            Defaults to 'all'.
        num_wavelengths (int, optional): If set, adds this many uniformly
            sampled wavelengths within [min, max] of system wavelengths,
            merged with and deduplicating against the native set.
            Defaults to None.

    Attributes:
        focal_lengths: Array of focal lengths (mm) per wavelength.
        focal_shifts: Array of focal shifts relative to primary (mm).
        normalized_focal_shifts: focal_shifts / primary_focal_length.
        primary_focal_length: Focal length at primary wavelength (mm).
        primary_wavelength: Primary wavelength (µm).
        max_shift: Maximum absolute focal shift (mm).
    """

    def __init__(self, optic, wavelengths="all", num_wavelengths=None):
        self.num_wavelengths = num_wavelengths
        if num_wavelengths is not None:
            native = [w.value for w in optic.wavelengths.wavelengths]
            wmin, wmax = min(native), max(native)
            extra = list(be.to_numpy(be.linspace(wmin, wmax, num_wavelengths)))
            combined = sorted({round(v, 9) for v in native + extra})
            wavelengths = combined
        super().__init__(optic, wavelengths)

    def _generate_data(self):
        if len(self.wavelengths) < 2:
            raise ValueError(
                "ChromaticFocalShift requires at least 2 wavelengths."
            )

        primary_wl = self.optic.primary_wavelength
        z_start = self.optic.paraxial.surfaces.positions[1] - 1

        data = []
        for wp in self.wavelengths:
            y, u = self.optic.paraxial.trace_generic(1.0, 0.0, z_start, wp.value)
            fl = (-y[0] / u[-1])[0]
            data.append(fl)

        fl_array = be.array([be.to_numpy(fl).item() for fl in data])

        primary_idx = min(
            range(len(self.wavelengths)),
            key=lambda i: abs(self.wavelengths[i].value - primary_wl),
        )
        primary_fl = fl_array[primary_idx]

        self.focal_lengths = fl_array
        self.focal_shifts = fl_array - primary_fl
        self.primary_focal_length = primary_fl
        self.primary_wavelength = primary_wl
        self.normalized_focal_shifts = self.focal_shifts / primary_fl
        self.max_shift = be.max(be.abs(self.focal_shifts))

        return data

    def view(
        self,
        fig_to_plot_on: Figure | None = None,
        figsize: tuple[float, float] = (7, 5),
    ) -> tuple[Figure, Axes]:
        """Plot focal shift (mm) vs. wavelength (µm).

        Args:
            fig_to_plot_on (Figure, optional): Figure to embed in. Defaults to None.
            figsize (tuple, optional): Figure size. Defaults to (7, 5).

        Returns:
            tuple[Figure, Axes]: The figure and axes.
        """
        is_gui_embedding = fig_to_plot_on is not None
        if is_gui_embedding:
            current_fig = fig_to_plot_on
            current_fig.clear()
            ax = current_fig.add_subplot(111)
        else:
            current_fig, ax = plt.subplots(figsize=figsize)

        wavelength_values = [wp.value for wp in self.wavelengths]
        shifts_np = be.to_numpy(self.focal_shifts)

        ax.plot(wavelength_values, shifts_np, "C0-o", markersize=4, zorder=10)
        ax.axvline(
            x=self.primary_wavelength,
            color="k",
            linewidth=0.8,
            linestyle="--",
            label=f"Primary {self.primary_wavelength:.4f} µm",
        )
        ax.axhline(y=0, color="k", linewidth=0.5)

        ax.set_xlabel("Wavelength (µm)")
        ax.set_ylabel("Focal Shift (mm)")
        ax.set_title("Chromatic Focal Shift")
        ax.legend(bbox_to_anchor=(1.05, 0.5), loc="center left")
        ax.grid(True)
        current_fig.tight_layout()

        if is_gui_embedding and hasattr(current_fig, "canvas"):
            current_fig.canvas.draw_idle()
        return current_fig, ax


class LateralColor(BaseAnalysis):
    """Chief ray image height difference across wavelengths at each field point.

    Measured at the system's current image surface (fixed, not re-focused per
    wavelength).

    Args:
        optic (Optic): The optic object to analyze.
        wavelengths (str or list, optional): Wavelengths to analyze.
            Defaults to 'all'.
        num_wavelengths (int, optional): If set, adds this many uniformly
            sampled wavelengths within [min, max] of system wavelengths,
            merged with and deduplicating against the native set.
            Defaults to None.

    Attributes:
        fields: Array of normalized field y-values.
        image_heights: 2D array (num_fields x num_wavelengths) of image heights.
        lateral_color: 2D array (num_fields x num_wavelengths) of lateral color.
        valid_mask: 2D boolean array (num_fields x num_wavelengths).
        primary_wavelength: Primary wavelength (µm).
        max_lateral_color: Maximum absolute lateral color across valid values (mm).
    """

    def __init__(self, optic, wavelengths="all", num_wavelengths=None):
        self.num_wavelengths = num_wavelengths
        if num_wavelengths is not None:
            native = [w.value for w in optic.wavelengths.wavelengths]
            wmin, wmax = min(native), max(native)
            extra = list(be.to_numpy(be.linspace(wmin, wmax, num_wavelengths)))
            combined = sorted({round(v, 9) for v in native + extra})
            wavelengths = combined
        super().__init__(optic, wavelengths)

    def _generate_data(self):
        if len(self.wavelengths) < 2:
            raise ValueError(
                "LateralColor requires at least 2 wavelengths."
            )

        primary_wl = self.optic.primary_wavelength
        field_coords = self.optic.fields.get_field_coords()
        num_fields = len(field_coords)

        Hx_arr = be.array([float(fx) for fx, fy in field_coords])
        Hy_arr = be.array([float(fy) for fx, fy in field_coords])
        Px_arr = be.zeros(num_fields)
        Py_arr = be.zeros(num_fields)

        data = []
        image_heights_list = []

        for wp in self.wavelengths:
            self.optic.trace_generic(
                Hx=Hx_arr, Hy=Hy_arr, Px=Px_arr, Py=Py_arr,
                wavelength=wp.value,
            )
            y_img = be.copy(self.optic.surfaces.y[-1, :])
            data.append(y_img)
            image_heights_list.append(y_img)

        # Build 2D arrays (num_fields x num_wavelengths)
        image_heights_2d = be.stack(image_heights_list, axis=1)

        primary_idx = min(
            range(len(self.wavelengths)),
            key=lambda i: abs(self.wavelengths[i].value - primary_wl),
        )
        primary_heights = image_heights_list[primary_idx]

        # lateral_color[f, w] = height(f, w) - height(f, primary)
        primary_col = be.stack(
            [primary_heights for _ in range(len(self.wavelengths))], axis=1
        )
        lateral_color_2d = image_heights_2d - primary_col

        valid_mask_2d = be.isfinite(image_heights_2d)

        lc_valid = be.where(valid_mask_2d, be.abs(lateral_color_2d), be.zeros(1))
        max_lc = be.max(lc_valid)

        self.fields = be.array([float(fy) for fx, fy in field_coords])
        self.image_heights = image_heights_2d
        self.lateral_color = lateral_color_2d
        self.valid_mask = valid_mask_2d
        self.primary_wavelength = primary_wl
        self.max_lateral_color = max_lc

        return data

    def view(
        self,
        fig_to_plot_on: Figure | None = None,
        figsize: tuple[float, float] = (7, 5),
    ) -> tuple[Figure, Axes]:
        """Plot lateral color (mm) vs. wavelength (µm), one curve per field.

        Args:
            fig_to_plot_on (Figure, optional): Figure to embed in. Defaults to None.
            figsize (tuple, optional): Figure size. Defaults to (7, 5).

        Returns:
            tuple[Figure, Axes]: The figure and axes.
        """
        is_gui_embedding = fig_to_plot_on is not None
        if is_gui_embedding:
            current_fig = fig_to_plot_on
            current_fig.clear()
            ax = current_fig.add_subplot(111)
        else:
            current_fig, ax = plt.subplots(figsize=figsize)

        wavelength_values = [wp.value for wp in self.wavelengths]
        lc_np = be.to_numpy(self.lateral_color)
        fields_np = be.to_numpy(self.fields)

        for i, fy in enumerate(fields_np):
            ax.plot(
                wavelength_values,
                lc_np[i, :],
                f"C{i}-o",
                markersize=4,
                zorder=10,
                label=f"Field {fy:.4f}",
            )

        ax.axvline(
            x=self.primary_wavelength,
            color="k",
            linewidth=0.8,
            linestyle="--",
            label=f"Primary {self.primary_wavelength:.4f} µm",
        )
        ax.axhline(y=0, color="k", linewidth=0.5)

        ax.set_xlabel("Wavelength (µm)")
        ax.set_ylabel("Lateral Color (mm)")
        ax.set_title("Lateral Color")
        ax.legend(bbox_to_anchor=(1.05, 0.5), loc="center left")
        ax.grid(True)
        current_fig.tight_layout()

        if is_gui_embedding and hasattr(current_fig, "canvas"):
            current_fig.canvas.draw_idle()
        return current_fig, ax
