import lephare as lp
import numpy as np
from matplotlib import pylab as plt
from scipy import integrate as sciint
import glob, time


def run_example_of_magsvc():
    config_file = lp.default_cosmos_config.copy()
    config_file["Z_STEP"] = "0.04,0.,7."
    keymap = lp.all_types_to_keymap(config_file)
    # Get the auxiliary files required.
    lp.data_retrieval.get_auxiliary_data(
        keymap=keymap,
        additional_files=[
            "sed/STAR/BD_NEW/lte012.0-4.0-0.0a+0.0.BT-Settl.spec.txt",
            "sed/GAL/COSMOS_SED/*",
        ],
    )

    # we can write the config to a file to keep a record
    config_filename = "./config_file.para"
    lp.write_para_config(keymap, config_filename)
    allFlt = lp.FilterSvc.from_config(config_filename)

    sed = lp.GalSED("test", 0)
    # sed.read(f"{lp.LEPHAREDIR}/sed/STAR/BD_NEW/lte012.0-4.0-0.0a+0.0.BT-Settl.spec.txt")
    sed.read(f"{lp.LEPHAREDIR}/examples/COSMOS_MOD.list")

    # opavec = lp.GalMag.read_opa()

    # We need the full previous stages to get the mags
    filterLib = lp.Filter(config_file=config_filename)
    # create the filter set
    filterLib.run()

    sedlib = lp.Sedtolib(config_keymap=keymap)
    # create the star library
    sedlib.run(typ="STAR", star_sed="$LEPHAREDIR/sed/STAR/STAR_MOD_ALL.list")
    # create the QSO library
    sedlib.run(
        typ="QSO",
        qso_sed="$LEPHAREDIR/sed/QSO/SALVATO09/AGN_MOD.list",
        gal_lib="LIB_QSO",
    )
    # create the galaxy library
    sedlib.run(
        typ="GAL", gal_sed="$LEPHAREDIR/examples/COSMOS_MOD.list", gal_lib="LIB_GAL"
    )

    # Create a magnitude library
    # Use the SED library to create a magnitude library
    maglib = lp.MagGal(config_file=config_filename, config_keymap=keymap)
    maglib.run(
        typ="GAL",
        lib_ascii="YES",
        gal_lib_in="LIB_GAL",
        gal_lib_out="VISTA_COSMOS_FREE",
        mod_extinc="18,26,26,33,26,33,26,33",
        extinc_law="SMC_prevot.dat,SB_calzetti.dat,SB_calzetti_bump1.dat,SB_calzetti_bump2.dat",
        em_lines="EMP_UV",
        em_dispersion="0.5,0.75,1.,1.5,2.",
    )

    # calculate synthetic magnitudes
    # mag = lp.MagSvc.from_config("Gal", config_file)

    # newsed = mag.make_maglib(sed)

    # newsed[0].mag

    print("DONE")

    return


if __name__ == "__main__":
    sed = run_example_of_magsvc()

    print("Done.")
