# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# Copyright 2021-2023, Ben Cardoen
import argparse
import logging
import os
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
lgr = logging.getLogger('global')
lgr.setLevel(logging.INFO)
lgr = None

import pandas as pd
import os
import numpy as np
import scipy
import glob
from scipy.signal import argrelextrema
from copy import copy
from scipy.stats import kurtosis
from scipy.stats import skew
from scipy import stats
from sklearn.covariance import EmpiricalCovariance, MinCovDet



def vesiclefilter(_df, K=2, LS=9, RMV=0.2, vesicle=False, minsize_vesicle=8):
    """
    This function processes a DataFrame (from loaddata), and filters it for vesicles.
    Vesicles are considered objects in the mitochondria channel with e^size < LS & mean(intensity) < rmv
    IOW, small and faint.

    Args:
    - K (int): Minimum size of contact
    - LS (float): Threshold size of adjacent mitochondria (LN scale, so e^{ls})
    - RMV (float): Mean intensity of adjacent mitochondria
    - vesicle (bool): True if you want to **KEEP** vesicle only
    - minsize_vescile (int): If vesicle, minimum size of mitochondria
    - alphav (float): The alpha value to filter the dataframes. Default is 0.05.
    
    Returns:
    - DF (pandas.DataFrame): The concatenated dataframe of all the dataframes found in the path.
    """
    _df = _df.copy()
    _df=_df[_df['skeletonsurface'] >0].copy()
    getlogger().info("Filtering ... Keeping vesicles = {} Size of mito {} Intensity {} Size of contact {}".format(vesicle, LS, RMV, K))
    if vesicle:
        FDF = _df[_df['volume'] > K].copy()
        FDF['rmv'] = FDF['adj_mito_vol_fuzzy'] / FDF['adj_mito_vol']
        FDF['ls'] = np.log(FDF['adj_mito_vol'])
        FDF['LV'] = np.log(FDF['volume'])
        FDF['c_to_m'] = FDF['volume'] / FDF['adj_mito_vol']
        VDF=FDF[(FDF['ls'] <= LS) & (FDF['rmv'] <= RMV) ].copy()
        VDF=VDF[(VDF['ls'] > np.log(minsize_vesicle))].copy()
        return VDF.copy()
    else:
        FDF = _df[_df['volume'] > K].copy()
        FDF['rmv'] = FDF['adj_mito_vol_fuzzy'] / FDF['adj_mito_vol']
        FDF['ls'] = np.log(FDF['adj_mito_vol'])
        FDF['LV'] = np.log(FDF['volume'])
        FDF['c_to_m'] = FDF['volume'] / FDF['adj_mito_vol']
#         Filtered_SZ_DF = FDF[(FDF['ls'] > LS) | (FDF['rmv']>RMV)].copy()
        Filtered_Large_DF = FDF[(FDF['ls'] > LS) | (FDF['rmv']>RMV)].copy()
        getlogger().info("{:.2f} % dropped".format((1-len(Filtered_Large_DF)/len(FDF))*100))
        return Filtered_Large_DF.copy()

def prefix(x, pfix=""):
    return "{}_{}".format(pfix, x)



def getcontents(_pth):
    fullpaths = map(lambda name: os.path.join(_pth, name), os.listdir(_pth))
    return fullpaths

def getcontacttype(fname):
    for t in targets:
        if t in fname:
            return t
    return None

def loaddata(path, alphav=0.05):
    """
    This function loads data from a given path and returns a concatenated dataframe of all the dataframes found in the path.
    The function filters the dataframes based on the given alpha value.
    path should be the top (experiment) directory of output generated by MCS detect.
    E.g.
    - experiment [path]
        - replicate (integer)
            - Series001 (cell nr, last 3 characters integer)
                - Alpha value (0.001, 0.05, ...)
    
    Args:
    - path (str): The path to the directory containing the dataframes.
    - alphav (float): The alpha value to filter the dataframes. Default is 0.05.
    
    Returns:
    - DF (pandas.DataFrame): The concatenated dataframe of all the dataframes found in the path.
    """
    _lgr = getlogger()
    udfs = []
    for replicatepath in getcontents(path):
        replicatenr = int(replicatepath.split(os.sep)[-1])
        for treatmentpath in getcontents(replicatepath):
            tmt = os.path.basename(treatmentpath)
            celltype=tmt
            for series in getcontents(treatmentpath):
                w=2
                # seriedescriptor = series.split(os.sep)[-1][-3:]
                seriedescriptor = series.split(os.sep)[-1][len("series"):]
                snr = int(seriedescriptor)
                assert(snr > 0)
                # _lgr.info("Celltype {} Replicate {} Window size {} cell nr {} ".format(celltype, replicatenr, w, snr))
                for alphadir in getcontents(series):
                    a = alphadir.split(os.sep)[-1]
                    av=float(a)
                    if av != alphav:
                        getlogger().debug("Alpha value not expected {} -- ignoring".format(av))
                        continue 

                    _lgr.info("Celltype {} Replicate {} Window size {} Cell number {} alpha {}".format(celltype, replicatenr, w, snr, a))
                    csvs = glob.glob("{}/*eroded*.csv".format(alphadir))
                    
                    if len(csvs) != 1:
                        _lgr.error("No data for {}".format(alphadir))
                        _lgr.error("PLEASE CHECK THAT MCS DETECT COMPLETED PROCESSING")
                        continue
                    _df = pd.read_csv(csvs[0])
                    _df['replicate'] = replicatenr
                    _df['serie'] = snr
                    _df['celltype'] = celltype
                    udfs.append(_df)
    _lgr.info("Have a total of {} dataframes".format(len(udfs)))
    if len(udfs) == 0:
        _lgr.error("NO DATA ???")
        exit(-1)
    _DF = pd.concat(udfs)
    cs = ['adj_mito_vol', 'adj_mito_vol_fuzzy']
    _DF['rmv']=_DF[cs[1]] / _DF[cs[0]]
    _DF['ls']=np.log(_DF[cs[0]])                
    _DF = _DF.fillna(0) # Fix NaN in kurtosis of 1   
    _DF=_DF[_DF['skeletonsurface'] >0].copy()
    _DF['experiment'] = path.split(os.path.sep)[-1]
    return _DF

nq3 = lambda x : np.quantile(x, 0.75)
nq9 = lambda x : np.quantile(x, 0.90)
nq95 = lambda x : np.quantile(x, 0.95)
nq99 = lambda x : np.quantile(x, 0.99)
nq1 = lambda x : np.quantile(x, 0.25)


def filterdf(df, selected, column='celltype'):
    xdf = df.loc[df[column].isin(selected)]
    return xdf.copy()

def postprocess_sampled(_df):
#     CUBEDF =  pd.read_csv(os.path.join(path, "all.csv"))
    CUBEDF=_df.copy()
    CUBEDF['ratio_cf_to_mf'] = CUBEDF['ctsurface']/CUBEDF['mtsurface'] * 100
    CUBEDF['mean_mito'] = CUBEDF['mitosum']/CUBEDF['mitvol']
    CUBEDF['mean_spear']=CUBEDF['contactsum'] / CUBEDF['contactvol']
    CUBEDF['mean_spear'].fillna(0, inplace=True)
    return CUBEDF.copy()


def aggregate_full(df):
    ### Data is organized by >Replicate>Celltype>Serienr
    q = df.groupby(
        ['celltype', 'serie', 'replicate', 'experiment']
    ).agg(
        {
            'LV' : ['mean', 'std', 'count', 'sum', 'skew', pd.Series.kurt],
            'volume' : ['mean', 'median', 'std', 'count', 'sum', 'skew', 'max', pd.Series.kurt, nq3, nq9, nq95, nq99],
            'weighted' : ['mean', 'std', 'count', 'sum', 'skew', pd.Series.kurt],
            'geometricmean' : ['mean','std', pd.Series.kurt],
            'geometricstd' : ['mean','std'],
            'skeletonsurface' : ['mean','std','count', 'sum', 'max', pd.Series.kurt, nq3, nq9],
            'adj_mito_vol' : ['mean','std','count', 'sum', 'max'],
            'adj_mito_vol_fuzzy' : ['mean','std','count', 'sum'],
            'zposition' : ['mean','std', 'sum'],
            'height' : ['mean','std','sum'],
            'xyspan' : ['mean','std','sum'],
            'planar' : ['mean','std', 'sum'],
            'sphericity' : ['mean','std', 'sum'],
            'anisotropy' : ['mean','std', 'sum'],
            'distancetocentroid' : ['mean','std', 'sum'],
            'normalizeddistancetocentroid' : ['mean','std', 'sum'],
            'normalizedzposition' : ['mean','std', 'sum'],
            'rmv' : ['mean','std', 'sum'],
            'c_to_m' : ['mean','std', 'sum'],
        }
        ).reset_index()
    q.columns = [' '.join(col).strip() for col in q.columns.values]
    #q[]
    q['Volume Q95'] = q['volume <lambda_2>']
    q['number of contacts'] = q['volume count']
    # Rename NQ to Vol95
    return q

def describedf(_df):
    _df = _df.copy()
    getlogger().info("Describing the collected data --- PLEASE CHECK IF THIS MATCHES YOUR ASSUMPTIONS")
    getlogger().info("Unique replicates: {}".format(np.unique(_df['replicate'])))
    # getlogger().info(np.unique(_df['replicate']))
    getlogger().info("Unique celltypes {}".format(np.unique(_df['celltype'])))
    # getlogger().info(np.unique(_df['celltype']))
    cts = np.unique(_df['celltype'])
    for ct in cts:
        # getlogger().info(ct)
        CDF = filterdf(_df.copy(), [ct])
        for r in np.unique(_df['replicate']):
            # getlogger().info("For replicate {} have a total of {} cells".format(r, len(CDF[CDF['replicate'] == r])))
            SDF=CDF[CDF['replicate'] == r].copy()
            series = np.unique(SDF['serie'])
            getlogger().info("For celltype {} have a total of {} cells for replicate {}".format(ct, len(series), r))


# From https://github.com/bencardoen/ERGO.py/blob/main/src/gconf.py
def initlogger(configuration):
    global lgr
    if lgr is None:
        lgr = logging.getLogger('global')
    if 'logdir' in configuration:
        fh = logging.FileHandler(os.path.join(configuration['logdir'], 'svrg.log'))
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter("[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s")
        fh.setFormatter(formatter)
        lgr.addHandler(fh)
    lgr.setLevel(logging.INFO)
    return lgr

# From https://github.com/bencardoen/ERGO.py/blob/main/src/gconf.py
def getlogger():
    global lgr
    if lgr is None:
        return initlogger({})
    return lgr



def run(args):
    dataframe = loaddata(args.inputdirectory, args.alpha)
    filtered=vesiclefilter(dataframe, 2, args.lnsize, args.mitoint, False, 8)
    getlogger().info("Data has been loaded and filtered ... saving to {}".format(args.outputdirectory))
    dataframe.to_csv(os.path.join(args.outputdirectory, "contacts_unfiltered.csv"))
    filtered.to_csv(os.path.join(args.outputdirectory, "contacts_filtered_novesicles.csv"))
    getlogger().info("Aggregating per cell --> Mean, Q95 Volume and so on...")
    aggregated = aggregate_full(filtered)
    getlogger().info("Describing your data -- Ensure this matches your expected number of conditions and cells !!")
    describedf(aggregated)
    getlogger().info("Saving to{}".format(os.path.join(args.outputdirectory, "contacts_aggregated.csv")))
    aggregated.to_csv(os.path.join(args.outputdirectory, "contacts_aggregated.csv"))
    lgr.info("Done !!")
    # load sampled data csvs
    # postprocess
    # save


import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This script process output from MCS detect.')
    # Add arguments
    parser.add_argument('--inputdirectory', required=True, help='path to output of MCSDETECT')
    parser.add_argument('--outputdirectory', required=True, help='path to outputdirectory to save curated csvs')
    parser.add_argument('--lnsize', type=float, default=9, help='Minimum size of adjacent mitochondria (natural log, default 9)')
    parser.add_argument('--mitoint', type=float, default=0.2, help='Minimum intensity (mean) of adjacent mitochondria (default 0.2)')
    parser.add_argument('--alpha', type=float, default=0.05, help='Alpha value to load (0.05 is default)')
    args = parser.parse_args()
    lgr=getlogger()
    for arg in vars(args):
        lgr.info("{} --> {}".format(arg, getattr(args, arg)))

    if not os.path.exists(args.inputdirectory) or not os.path.exists(args.outputdirectory):
        lgr.error("Input path or output path does not exist")
        exit(-1)

    lnsize = args.lnsize
    mitoint = args.mitoint
    alpha = args.alpha
    run(args)
