import pyarrow.parquet as pq
from astropy.table import Table
from roman_photoz.roman_catalog_process import RomanCatalogProcess
from roman_photoz.create_simulated_catalog import SimulatedCatalog

PHOTOZ_COLS = [
    "photoz",
    "photoz_gof",
    "photoz_high68",
    "photoz_high90",
    "photoz_high99",
    "photoz_low68",
    "photoz_low90",
    "photoz_low99",
    "photoz_sed",
]


def extract_metadata(filename, backend):
    if backend == "pyarrow":
        tab = pq.read_table(filename)
        schema = tab.schema
        colnames = schema.names

        def get_field(name):
            return schema.field(name)

        def get_unit(meta):
            # return "None" if key is missing instead of "NOT FOUND"
            if b"unit" not in meta:
                return "None"
            return meta.get(b"unit").decode("utf-8")

        def get_desc(meta):
            return meta.get(b"description", b"NOT FOUND").decode("utf-8")
    else:
        tab = Table.read(filename)
        colnames = tab.colnames

        def get_field(name):
            return tab[name]

        def get_unit(col):
            # since astropy .unit is now None, we stringify it to "None"
            return str(col.unit)

        def get_desc(col):
            return col.info.description if col.info.description else "NOT FOUND"

    metadata_dict = {}
    for col_name in PHOTOZ_COLS:
        if col_name in colnames:
            field = get_field(col_name)
            if backend == "pyarrow":
                meta = field.metadata if field.metadata else {}
                unit = get_unit(meta)
                description = get_desc(meta)
            else:
                unit = get_unit(field)
                description = get_desc(field)

            # notice that a column is "found" if it has a description.
            # (a unit is now allowed to be "None")
            found = description != "NOT FOUND"
            metadata_dict[col_name] = {
                "unit": unit,
                "description": description,
                "found": found,
            }
        else:
            metadata_dict[col_name] = {"found": False, "column_exists": False}
    return metadata_dict


def compare_metadata(pyarrow_meta, astropy_meta):
    all_cols = set(pyarrow_meta.keys()) | set(astropy_meta.keys())
    consistent = True
    for col_name in sorted(all_cols):
        pa_found = pyarrow_meta.get(col_name, {}).get("found", False)
        astropy_found = astropy_meta.get(col_name, {}).get("found", False)

        if pa_found and astropy_found:
            pa_unit = pyarrow_meta[col_name]["unit"]
            astropy_unit = astropy_meta[col_name]["unit"]

            # Change: Simplified matching logic.
            # Both should now naturally result in the string "None"
            units_match = pa_unit == astropy_unit

            desc_match = (
                pyarrow_meta[col_name]["description"]
                == astropy_meta[col_name]["description"]
            )
            if not (units_match and desc_match):
                consistent = False
        elif pa_found != astropy_found:
            consistent = False
        else:
            # If both are not found, it's technically consistent (both missing)
            pass

    return consistent


def test_metadata_preservation(tmp_path):
    output_filename = "test_result.parquet"
    simulated_catalog_filename = "simulated_catalog.parquet"

    simulated_catalog = SimulatedCatalog(
        nobj=100,
        seed=42,
    )
    simulated_catalog.process(
        output_path=tmp_path,
        output_filename=simulated_catalog_filename,
    )

    # catalog processing
    rcp = RomanCatalogProcess()
    rcp.process(
        input_filename=tmp_path / simulated_catalog_filename,
        output_filename=tmp_path / output_filename,
    )

    pyarrow_meta = extract_metadata(tmp_path / output_filename, "pyarrow")
    astropy_meta = extract_metadata(tmp_path / output_filename, "astropy")

    pyarrow_count = sum(1 for m in pyarrow_meta.values() if m.get("found", False))
    astropy_count = sum(1 for m in astropy_meta.values() if m.get("found", False))

    consistent = compare_metadata(pyarrow_meta, astropy_meta)

    assert pyarrow_count == 9, "Not all photoz columns have metadata in PyArrow"
    assert astropy_count == 9, "Not all photoz columns have metadata in Astropy"
    assert consistent, "Metadata is not consistent between PyArrow and Astropy"
