"""Test cases for the core module."""
import numpy as np
import numpy.typing as npt
import pint
import pytest
import xarray as xr

from ussa1976 import ureg
from ussa1976.core import AR_7
from ussa1976.core import compute_high_altitude
from ussa1976.core import compute_levels_temperature_and_pressure_low_altitude
from ussa1976.core import compute_low_altitude
from ussa1976.core import compute_mean_molar_mass_high_altitude
from ussa1976.core import compute_number_densities_high_altitude
from ussa1976.core import compute_temperature_gradient_high_altitude
from ussa1976.core import compute_temperature_high_altitude
from ussa1976.core import create
from ussa1976.core import H
from ussa1976.core import init_data_set
from ussa1976.core import M
from ussa1976.core import M0
from ussa1976.core import make
from ussa1976.core import O2_7
from ussa1976.core import O_7
from ussa1976.core import SPECIES
from ussa1976.core import to_altitude
from ussa1976.core import VARIABLES


def test_make() -> None:
    """Returned data set has expected data."""
    # default constructor
    profile = make()

    assert profile["z_level"].values[0] == 0.0
    assert profile["z_level"].values[-1] == 100000.0
    assert profile.dims["z_layer"] == 50
    assert profile.dims["species"] == 12

    # custom levels altitudes
    profile = make(levels=ureg.Quantity(np.linspace(2.0, 15.0, 51), "km"))

    assert profile.dims["z_layer"] == 50
    assert profile["z_level"].values[0] == 2000.0
    assert profile["z_level"].values[-1] == 15000.0
    assert profile.dims["species"] == 12

    # custom number of layers
    profile = make(levels=ureg.Quantity(np.linspace(0.0, 150.0, 37), "kilometers"))

    assert profile.dims["z_layer"] == 36
    assert profile["z_level"].values[0] == 0.0
    assert profile["z_level"].values[-1] == 150000.0
    assert profile.dims["species"] == 12

    profile = make(levels=ureg.Quantity(np.linspace(0.0, 80.0, 2), "kilometers"))

    assert profile.dims["z_layer"] == 1
    assert profile["z_level"].values[0] == 0.0
    assert profile["z_level"].values[-1] == 80000.0
    assert profile.dims["species"] == 12


def test_make_invalid_levels() -> None:
    """Raises a ValueError on invalid level altitudes."""
    with pytest.raises(ValueError):
        make(levels=np.linspace(-4000, 50000))

    with pytest.raises(ValueError):
        make(levels=np.linspace(500.0, 5000000.0))


@pytest.fixture
def test_altitudes() -> pint.Quantity:
    """Test altitudes fixture."""
    return ureg.Quantity(np.linspace(0.0, 100000.0, 101), "meter")


def test_create(test_altitudes: npt.NDArray[np.float64]) -> None:
    """Creates a data set with expected data."""
    z = ureg.Quantity(np.linspace(0.0, 100000.0, 101), "meter")

    ds = create(z=test_altitudes)
    assert all([v in ds.data_vars for v in VARIABLES])

    variables = ["p", "t", "n", "n_tot"]
    ds = create(z, variables=variables)

    dims = ds.dims
    assert len(dims) == 2
    assert "z" in dims
    assert "species" in dims

    coords = ds.coords
    assert len(coords) == 2
    assert (coords["z"] == z.magnitude).all()
    assert [s for s in coords["species"]] == [s for s in SPECIES]

    for var in variables:
        assert var in ds

    assert all(
        [
            x in ds.attrs
            for x in ["convention", "title", "history", "source", "references"]
        ]
    )


def test_create_invalid_variables(test_altitudes: npt.NDArray[np.float64]) -> None:
    """Raises when invalid variables are given."""
    invalid_variables = ["p", "t", "invalid", "n"]
    with pytest.raises(ValueError):
        create(z=test_altitudes, variables=invalid_variables)


def test_create_invalid_z() -> None:
    """Raises when invalid altitudes values are given."""
    with pytest.raises(ValueError):
        create(z=np.array([-5.0]))

    with pytest.raises(ValueError):
        create(z=np.array(1000001.0))


def test_create_below_86_km_layers_boundary_altitudes() -> None:
    """
    Produces correct results.

    We test the computation of the atmospheric variables (pressure,
    temperature and mass density) at the level altitudes, i.e. at the model
    layer boundaries. We assert correctness by comparing their values with the
    values from the table 1 of the U.S. Standard Atmosphere 1976 document.
    """
    z = to_altitude(np.array(H))
    ds = create(z, variables=["p", "t", "rho"])

    level_temperature = np.array(
        [288.15, 216.65, 216.65, 228.65, 270.65, 270.65, 214.65, 186.87]
    )
    level_pressure = np.array(
        [101325.0, 22632.0, 5474.8, 868.01, 110.90, 66.938, 3.9564, 0.37338]
    )
    level_mass_density = np.array(
        [
            1.225,
            0.36392,
            0.088035,
            0.013225,
            0.0014275,
            0.00086160,
            0.000064261,
            0.000006958,
        ]
    )

    assert np.allclose(ds["t"].values, level_temperature, rtol=1e-4)
    assert np.allclose(ds["p"].values, level_pressure, rtol=1e-4)
    assert np.allclose(ds["rho"].values, level_mass_density, rtol=1e-3)


def test_create_below_86_km_arbitrary_altitudes() -> None:
    """
    Produces correct results.

    We test the computation of the atmospheric variables (pressure,
    temperature and mass density) at arbitrary altitudes. We assert correctness
    by comparing their values to the values from table 1 of the U.S. Standard
    Atmosphere 1976 document.
    """
    # The values below were selected arbitrarily from Table 1 of the document
    # such that there is at least one value in each of the 7 temperature
    # regions.
    h = np.array(
        [
            200.0,
            1450.0,
            5250.0,
            6500.0,
            9800.0,
            17900.0,
            24800.0,
            27100.0,
            37200.0,
            40000.0,
            49400.0,
            61500.0,
            79500.0,
            84000.0,
        ]
    )
    temperatures = np.array(
        [
            286.850,
            278.725,
            254.025,
            245.900,
            224.450,
            216.650,
            221.450,
            223.750,
            243.210,
            251.050,
            270.650,
            241.250,
            197.650,
            188.650,
        ]
    )
    pressures = np.array(
        [
            98945.0,
            85076.0,
            52239.0,
            44034.0,
            27255.0,
            7624.1,
            2589.6,
            1819.4,
            408.7,
            277.52,
            81.919,
            16.456,
            0.96649,
            0.43598,
        ]
    )
    mass_densities = np.array(
        [
            1.2017,
            1.0633,
            0.71641,
            0.62384,
            0.42304,
            0.12259,
            0.040739,
            0.028328,
            0.0058542,
            0.0038510,
            0.0010544,
            0.00023764,
            0.000017035,
            0.0000080510,
        ]
    )

    z = to_altitude(h)
    ds = create(z, variables=["t", "p", "rho"])

    assert np.allclose(temperatures, ds["t"].values, rtol=1e-4)
    assert np.allclose(pressures, ds["p"].values, rtol=1e-4)
    assert np.allclose(mass_densities, ds["rho"].values, rtol=1e-4)


def test_init_data_set() -> None:
    """Data set is initialised.

    Expected data variables are created and fill with nan values.
    Expected dimensions and coordinates are present.
    """

    def check_data_set(ds: xr.Dataset) -> None:
        """Check a data set."""
        for var in VARIABLES:
            assert var in ds
            assert np.isnan(ds[var].values).all()

        assert ds["n"].values.ndim == 2
        assert all(
            ds["species"].values
            == ["N2", "O2", "Ar", "CO2", "Ne", "He", "Kr", "Xe", "CH4", "H2", "O", "H"]
        )

    z1 = ureg.Quantity(np.linspace(0.0, 50000.0), "meter")
    ds1 = init_data_set(z1)
    check_data_set(ds1)

    z2 = ureg.Quantity(np.linspace(120000.0, 650000.0), "meter")
    ds2 = init_data_set(z2)
    check_data_set(ds2)

    z3 = ureg.Quantity(np.linspace(70000.0, 100000.0), "meter")
    ds3 = init_data_set(z3)
    check_data_set(ds3)


def test_compute_levels_temperature_and_pressure_low_altitude() -> None:
    """Computes correct level temperature and pressure values.

    The correct values are taken from :cite:`NASA1976USStandardAtmosphere`.
    """
    tb, pb = compute_levels_temperature_and_pressure_low_altitude()

    level_temperature = np.array(
        [288.15, 216.65, 216.65, 228.65, 270.65, 270.65, 214.65, 186.87]
    )
    level_pressure = np.array(
        [101325.0, 22632.0, 5474.8, 868.01, 110.90, 66.938, 3.9564, 0.37338]
    )

    assert np.allclose(tb, level_temperature, rtol=1e-3)
    assert np.allclose(pb, level_pressure, rtol=1e-3)


def rtol(
    v: npt.NDArray[np.float64], ref: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Compute a relative tolerance."""
    return np.array(np.abs(v - ref) / ref)


def test_compute_number_density() -> None:
    """Computes correct number density values at arbitrary level altitudes.

    The correct values are taken from :cite:`NASA1976USStandardAtmosphere`
    (table VIII, p. 210-215).
    """
    # the following altitudes values are chosen arbitrarily
    altitudes = ureg.Quantity(
        np.array(
            [
                86.0,
                90.0,
                95.0,
                100.0,
                110.0,
                120.0,
                150.0,
                200.0,
                300.0,
                400.0,
                500.0,
                600.0,
                700.0,
                800.0,
                900.0,
                1000.0,
            ]
        ),
        "km",
    )
    mask = altitudes.magnitude > 150.0

    # the corresponding number density values are from NASA (1976) - U.S.
    # Standard Atmosphere, table VIII (p. 210-215)
    values = {
        "N2": np.array(
            [
                1.13e20,
                5.547e19,
                2.268e19,
                9.210e18,
                1.641e18,
                3.726e17,
                3.124e16,
                2.925e15,
                9.593e13,
                4.669e12,
                2.592e11,
                1.575e10,
                1.038e9,
                7.377e7,
                5.641e6,
                4.626e5,
            ]
        ),
        "O": np.array(
            [
                O_7,
                2.443e17,
                4.365e17,
                4.298e17,
                2.303e17,
                9.275e16,
                1.780e16,
                4.050e15,
                5.443e14,
                9.584e13,
                1.836e13,
                3.707e12,
                7.840e11,
                1.732e11,
                3.989e10,
                9.562e9,
            ]
        ),
        "O2": np.array(
            [
                O2_7,
                1.479e19,
                5.83e18,
                2.151e18,
                2.621e17,
                4.395e16,
                2.750e15,
                1.918e14,
                3.942e12,
                1.252e11,
                4.607e9,
                1.880e8,
                8.410e6,
                4.105e5,
                2.177e4,
                1.251e3,
            ]
        ),
        "Ar": np.array(
            [
                AR_7,
                6.574e17,
                2.583e17,
                9.501e16,
                1.046e16,
                1.366e15,
                5.0e13,
                1.938e12,
                1.568e10,
                2.124e8,
                3.445e6,
                6.351e4,
                1.313e3,
                3.027e1,
                7.741e-1,
                2.188e-2,
            ]
        ),
        "He": np.array(
            [
                7.582e14,
                3.976e14,
                1.973e14,
                1.133e14,
                5.821e13,
                3.888e13,
                2.106e13,
                1.310e13,
                7.566e12,
                4.868e12,
                3.215e12,
                2.154e12,
                1.461e12,
                1.001e12,
                6.933e11,
                4.850e11,
            ]
        ),
        "H": np.array(
            [
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                3.767e11,
                1.630e11,
                1.049e11,
                8.960e10,
                8.0e10,
                7.231e10,
                6.556e10,
                5.961e10,
                5.434e10,
                4.967e10,
            ]
        ),
    }

    n = compute_number_densities_high_altitude(altitudes)

    assert np.allclose(n["N2"], values["N2"], rtol=0.01)
    # TODO: investigate the poor relative tolerance that is achieved here
    assert np.allclose(n["O"], values["O"], rtol=0.1)
    assert np.allclose(n["O2"], values["O2"], rtol=0.01)
    assert np.allclose(n["Ar"], values["Ar"], rtol=0.01)
    assert np.allclose(n["He"], values["He"], rtol=0.01)
    assert np.allclose(n["H"][mask], values["H"][mask], rtol=0.01)


def test_compute_mean_molar_mass() -> None:
    """Computes correct mean molar mass values.

    The correct values are taken from :cite:`NASA1976USStandardAtmosphere`.
    """
    # test call with scalar altitude
    assert compute_mean_molar_mass_high_altitude(90.0) == M0
    assert compute_mean_molar_mass_high_altitude(200.0) == M["N2"]

    # test call with array of altitudes
    z = np.linspace(86, 1000, 915)
    assert np.allclose(
        compute_mean_molar_mass_high_altitude(z), np.where(z <= 100.0, M0, M["N2"])
    )


def test_compute_temperature_above_86_km() -> None:
    """Compute correct temperature values.

    The correct values are taken from :cite:`NASA1976USStandardAtmosphere`.
    """
    # test call with scalar altitude
    assert np.isclose(compute_temperature_high_altitude(90.0), 186.87, rtol=1e-3)

    # test call with array of altitudes
    z = np.array([100.0, 110.0, 120.0, 130.0, 200.0, 500.0])  # km
    assert np.allclose(
        compute_temperature_high_altitude(z),
        np.array([195.08, 240.00, 360.0, 469.27, 854.56, 999.24]),
        rtol=1e-3,
    )


def test_compute_temperature_above_86_km_invalid_altitudes() -> None:
    """Raises when altitude is out of range."""
    with pytest.raises(ValueError):
        compute_temperature_high_altitude(altitude=10.0)


def test_compute_high_altitude_no_mask() -> None:
    """Returns a Dataset."""
    z = ureg.Quantity(np.linspace(86e3, 1000e3), "m")
    ds = init_data_set(z=z)
    compute_high_altitude(ds, mask=None, inplace=True)
    assert isinstance(ds, xr.Dataset)


def test_compute_high_altitude_not_inplace() -> None:
    """Returns a Dataset."""
    z = ureg.Quantity(np.linspace(86e3, 1000e3), "m")
    ds1 = init_data_set(z=z)
    ds2 = compute_high_altitude(ds1, mask=None, inplace=False)
    assert ds1 != ds2
    assert isinstance(ds2, xr.Dataset)


def test_compute_low_altitude() -> None:
    """Returns a Dataset."""
    z = ureg.Quantity(np.linspace(0, 86e3), "m")
    ds = init_data_set(z=z)
    compute_low_altitude(ds, mask=None, inplace=True)
    assert isinstance(ds, xr.Dataset)


def test_compute_low_altitude_not_inplace() -> None:
    """Returns a Dataset."""
    z = ureg.Quantity(np.linspace(0, 86e3), "m")
    ds1 = init_data_set(z=z)
    ds2 = compute_low_altitude(ds1, mask=None, inplace=False)
    assert ds1 != ds2
    assert isinstance(ds2, xr.Dataset)


def test_compute_temperature_gradient_high_altitude() -> None:
    """Raises ValueError when altitude is out of bounds."""
    with pytest.raises(ValueError):
        z = ureg.Quantity(1300e3, "m")
        compute_temperature_gradient_high_altitude(z)