import os
from pathlib import Path

import lephare as lp

LEPHAREDIR = os.environ.get("LEPHAREDIR", lp.LEPHAREDIR)
CWD = os.getcwd()

__all__ = ["default_roman_config"]

default_roman_config = {
    "STAR_SED": "sed/STAR/STAR_MOD_ALL.list",
    "STAR_LIB": "LIB_STAR",
    "STAR_LIB_IN": "LIB_STAR",
    "STAR_LIB_OUT": "STAR_COSMOS",
    "STAR_FSCALE": "3.432E-09",

    "QSO_SED": "sed/QSO/SALVATO09/AGN_MOD.list",
    "QSO_LIB": "LIB_QSO",
    "QSO_LIB_IN": "LIB_QSO",
    "QSO_LIB_OUT": "QSO_COSMOS",
    "QSO_FSCALE": "1.",

    "GAL_SED": f"sed/GAL/COSMOS_SED/COSMOS_MOD.list",
    "GAL_FSCALE": "1.",
    "GAL_LIB": "LIB_GAL",
    "GAL_LIB_IN": "LIB_GAL",
    "GAL_LIB_OUT": "GAL_COSMOS",
    "AGE_RANGE": "0.,15.e9",

    "FILTER_REP": f"{LEPHAREDIR}/filt",
    "FILTER_LIST": "roman/roman_F062.pb,roman/roman_F087.pb,roman/roman_F106.pb,roman/roman_F129.pb,roman/roman_F146.pb,roman/roman_F158.pb,roman/roman_F184.pb,roman/roman_F213.pb",  # noqa: E501
    "TRANS_TYPE": "1",  # photon-counting filters
    "FILTER_CALIB": "0,0,0,0,0,0,0,0",
    "FILTER_FILE": "filter_roman",

    "MAGTYPE": "AB",
    "ZGRID_TYPE": "0",
    "Z_STEP": "0.04,0.,4.0",
    "COSMOLOGY": "70,0.3,0.7",
    "MOD_EXTINC": "18,26,26,33,26,33,26,33",
    "EB_V": "0.01,0.05,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.5",
    "EXTINC_LAW": "SMC_prevot.dat,SB_calzetti.dat,SB_calzetti_bump1.dat,SB_calzetti_bump2.dat",
    "EM_LINES": "EMP_UV",
    "EM_DISPERSION": "0.5,0.75,1.,1.5,2.",
    "ADD_DUSTEM": "NO",
    "LIB_ASCII": "YES",

    "AUTO_ADAPT": "NO",

    "CAT_IN": "roman_simulated_catalog.parquet",
    "INP_TYPE": "F",
    "CAT_MAG": "AB",
    "CAT_FMT": "MEME",
    "CAT_LINES": "-99,-99",
    "CAT_TYPE": "LONG",
    "GLB_CONTEXT": "0",
    "FORB_CONTEXT": "-1",
    "ERR_SCALE": "0.02,0.02,0.02,0.02,0.02,0.02,0.02,0.02",  # noqa: E501
    "ERR_FACTOR": "1.5",
    "ADD_EMLINES": "0,10000",

    "ZPHOTLIB": "GAL_COSMOS,STAR_COSMOS,QSO_COSMOS",

    "CAT_OUT": "roman_simulated_catalog.out",
    "PARA_OUT": str(Path(__file__).parent / "data" / "default_roman_output.para"),
    "VERBOSE": "YES",
    "PDZ_TYPE": "BAY_ZG",
    "PDZ_OUT": "test",

    "RM_DISCREPANT_BD": "500",  # throw out a band if it has >500 chi^2.

    "MAG_ABS": "-24,-5",
    "MAG_ABS_QSO": "-30,-10",
    "MAG_REF": "3",  # F106
    "Z_RANGE": "0.0,99.99",
    "EBV_RANGE": "0,9",

    "ZFIX": "NO",
    "EXTERNALZ_FILE": "NONE",

    "Z_INTERP": "YES",
    "Z_METHOD": "BEST",

    "DZ_WIN": "0.25",
    "MIN_THRES": "0.1",


    "SPEC_OUT": "NO",
    "CHI2_OUT": "NO",

    "AUTO_ADAPT": "NO",
    "ADAPT_BAND": "5",
    "ADAPT_CONTEXT": "-1",
    "ADAPT_LIM": "1.5,23.0",
    "ADAPT_ZBIN": "0.01,6",
    "ADAPT_MODBIN": "1,1000",

    "FIR_LIB": "NONE",
    "FIR_LMIN": "7.0",
    "FIR_CONT": "-1",
    "FIR_SCALE": "-1",
    "FIR_FREESCALE": "YES",
    "FIR_SUBSTELLAR": "NO",

    "MABS_METHOD": "0",
    "MABS_CONTEXT": "-1",
    "MABS_REF": "0",
    "MABS_FILT": "-1",
    "MABS_ZBIN": "-1",
    "RF_COLORS": "-1,-1,-1,-1",
    "ADDITIONAL_MAG": "none",

    "LIMITS_ZBIN": "0,99",
    "LIMITS_MAPP_REF": "1",
    "LIMITS_MAPP_SEL": "1",
    "LIMITS_MAPP_CUT": "90",

}
