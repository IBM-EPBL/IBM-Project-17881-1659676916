import numpy as np

from ._contourpy import (
    ContourGenerator, FillType, LineType, Mpl2005ContourGenerator, Mpl2014ContourGenerator,
    SerialContourGenerator, ThreadedContourGenerator, ZInterp, max_threads,
)
from ._version import __version__
from .chunk import calc_chunk_sizes
from .enum_util import as_fill_type, as_line_type, as_z_interp

__all__ = [
    "__version__",
    "contour_generator",
    "max_threads",
    "FillType",
    "LineType",
    "ContourGenerator",
    "Mpl2005ContourGenerator",
    "Mpl2014ContourGenerator",
    "SerialContourGenerator",
    "ThreadedContourGenerator",
    "ZInterp",
]


# Simple mapping of algorithm name to class name.
_class_lookup = dict(
    mpl2005=Mpl2005ContourGenerator,
    mpl2014=Mpl2014ContourGenerator,
    serial=SerialContourGenerator,
    threaded=ThreadedContourGenerator,
)


def _remove_z_mask(z):
    z = np.ma.asarray(z, dtype=np.float64)  # Preserves mask if present.
    z = np.ma.masked_invalid(z, copy=False)

    if np.ma.is_masked(z):
        mask = np.ma.getmask(z)
    else:
        mask = None

    z = np.ma.getdata(z)
    return z, mask


def contour_generator(x=None, y=None, z=None, *, name="serial", corner_mask=None, line_type=None,
                      fill_type=None, chunk_size=None, chunk_count=None, total_chunk_count=None,
                      quad_as_tri=False, z_interp=ZInterp.Linear, thread_count=0):
    """Create and return a contour generator object.

    The class and properties of the contour generator are determined by the function arguments,
    with sensible defaults.

    Args:
        x (array-like of shape (ny, nx) or (nx,), optional): The x-coordinates of the ``z`` values.
            May be 2D with the same shape as ``z.shape``, or 1D with length ``nx = z.shape[1]``.
            If not specified are assumed to be ``np.arange(nx)``. Must be ordered monotonically.
        y (array-like of shape (ny, nx) or (ny,), optional): The y-coordinates of the ``z`` values.
            May be 2D with the same shape as ``z.shape``, or 1D with length ``ny = z.shape[0]``.
            If not specified are assumed to be ``np.arange(ny)``. Must be ordered monotonically.
        z (array-like of shape (ny, nx), may be a masked array): The 2D gridded values to calculate
            the contours of.  May be a masked array, and any invalid values (``np.inf`` or
            ``np.nan``) will also be masked out.
        name (str): Algorithm name, one of ``"serial"``, ``"threaded"``, ``"mpl2005"`` or
            ``"mpl2014"``, default ``"serial"``.
        corner_mask (bool, optional): Enable/disable corner masking, which only has an effect if
            ``z`` is a masked array. If ``False``, any quad touching a masked point is masked out.
            If ``True``, only the triangular corners of quads nearest these points are always masked
            out, other triangular corners comprising three unmasked points are contoured as usual.
            If not specified, uses the default provided by the algorithm ``name``.
        line_type (LineType, optional): The format of contour line data returned from calls to
            :meth:`~contourpy.ContourGenerator.lines`. If not specified, uses the default provided
            by the algorithm ``name``.
        fill_type (FillType, optional): The format of filled contour data returned from calls to
            :meth:`~contourpy.ContourGenerator.filled`. If not specified, uses the default provided
            by the algorithm ``name``.
        chunk_size (int or tuple(int, int), optional): Chunk size in (y, x) directions, or the same
            size in both directions if only one value is specified.
        chunk_count (int or tuple(int, int), optional): Chunk count in (y, x) directions, or the
            same count in both directions if only one value is specified.
        total_chunk_count (int, optional): Total number of chunks.
        quad_as_tri (bool): Enable/disable treating quads as 4 triangles, default ``False``.
            If ``False``, a contour line within a quad is a straight line between points on two of
            its edges. If ``True``, each full quad is divided into 4 triangles using a virtual point
            at the centre (mean x, y of the corner points) and a contour line is piecewise linear
            within those triangles. Corner-masked triangles are not affected by this setting, only
            full unmasked quads.
        z_interp (ZInterp): How to interpolate ``z`` values when determining where contour lines
            intersect the edges of quads and the ``z`` values of the central points of quads,
            default ``ZInterp.Linear``.
        thread_count (int): Number of threads to use for contour calculation, default 0. Threads can
            only be used with an algorithm ``name`` that supports threads (currently only
            ``name="threaded"``) and there must be at least the same number of chunks as threads.
            If ``thread_count=0`` and ``name="threaded"`` then it uses the maximum number of threads
            as determined by the C++11 call ``std::thread::hardware_concurrency()``. If ``name`` is
            something other than ``"threaded"`` then the ``thread_count`` will be set to ``1``.

    Return:
        :class:`~contourpy._contourpy.ContourGenerator`.

    Note:
        A maximum of one of ``chunk_size``, ``chunk_count`` and ``total_chunk_count`` may be
        specified.

    Warning:
        The ``name="mpl2005"`` algorithm does not implement chunking for contour lines.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z, mask = _remove_z_mask(z)

    # Check arguments: z.
    if z.ndim != 2:
        raise TypeError(f"Input z must be 2D, not {z.ndim}D")

    if z.shape[0] < 2 or z.shape[1] < 2:
        raise TypeError(f"Input z must be at least a (2, 2) shaped array, but has shape {z.shape}")

    ny, nx = z.shape

    # Check arguments: x and y.
    if x.ndim != y.ndim:
        raise TypeError(f"Number of dimensions of x ({x.ndim}) and y ({y.ndim}) do not match")

    if x.ndim == 0:
        x = np.arange(nx, dtype=np.float64)
        y = np.arange(ny, dtype=np.float64)
        x, y = np.meshgrid(x, y)
    elif x.ndim == 1:
        if len(x) != nx:
            raise TypeError(f"Length of x ({len(x)}) must match number of columns in z ({nx})")
        if len(y) != ny:
            raise TypeError(f"Length of y ({len(y)}) must match number of rows in z ({ny})")
        x, y = np.meshgrid(x, y)
    elif x.ndim == 2:
        if x.shape != z.shape:
            raise TypeError(f"Shapes of x {x.shape} and z {z.shape} do not match")
        if y.shape != z.shape:
            raise TypeError(f"Shapes of y {y.shape} and z {z.shape} do not match")
    else:
        raise TypeError(f"Inputs x and y must be None, 1D or 2D, not {x.ndim}D")

    # Check mask shape just in case.
    if mask is not None and mask.shape != z.shape:
        raise ValueError("If mask is set it must be a 2D array with the same shape as z")

    # Check arguments: name.
    if name not in _class_lookup:
        raise ValueError(f"Unrecognised contour generator name: {name}")

    # Check arguments: chunk_size, chunk_count and total_chunk_count.
    y_chunk_size, x_chunk_size = calc_chunk_sizes(
        chunk_size, chunk_count, total_chunk_count, ny, nx)

    cls = _class_lookup[name]

    # Check arguments: corner_mask.
    if corner_mask is None:
        # Set it to default, which is True if the algorithm supports it.
        corner_mask = cls.supports_corner_mask()
    elif corner_mask and not cls.supports_corner_mask():
        raise ValueError(f"{name} contour generator does not support corner_mask=True")

    # Check arguments: line_type.
    if line_type is None:
        line_type = cls.default_line_type
    else:
        line_type = as_line_type(line_type)

    if not cls.supports_line_type(line_type):
        raise ValueError(f"{name} contour generator does not support line_type {line_type}")

    # Check arguments: fill_type.
    if fill_type is None:
        fill_type = cls.default_fill_type
    else:
        fill_type = as_fill_type(fill_type)

    if not cls.supports_fill_type(fill_type):
        raise ValueError(f"{name} contour generator does not support fill_type {fill_type}")

    # Check arguments: quad_as_tri.
    if quad_as_tri and not cls.supports_quad_as_tri():
        raise ValueError(f"{name} contour generator does not support quad_as_tri=True")

    # Check arguments: z_interp.
    if z_interp is None:
        z_interp = ZInterp.Linear
    else:
        z_interp = as_z_interp(z_interp)

    if z_interp != ZInterp.Linear and not cls.supports_z_interp():
        raise ValueError(f"{name} contour generator does not support z_interp {z_interp}")

    # Check arguments: thread_count.
    if thread_count not in (0, 1) and not cls.supports_threads():
        raise ValueError(f"{name} contour generator does not support thread_count {thread_count}")

    # Prepare args and kwargs for contour generator constructor.
    args = [x, y, z, mask]
    kwargs = {
        "x_chunk_size": x_chunk_size,
        "y_chunk_size": y_chunk_size,
    }

    if name not in ("mpl2005", "mpl2014"):
        kwargs["line_type"] = line_type
        kwargs["fill_type"] = fill_type

    if cls.supports_corner_mask():
        kwargs["corner_mask"] = corner_mask

    if cls.supports_quad_as_tri():
        kwargs["quad_as_tri"] = quad_as_tri

    if cls.supports_z_interp():
        kwargs["z_interp"] = z_interp

    if cls.supports_threads():
        kwargs["thread_count"] = thread_count

    # Create contour generator.
    cont_gen = cls(*args, **kwargs)

    return cont_gen
