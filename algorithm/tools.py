# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode:nil -*-
# vi: set ft=python sts=4 sw=4 et:

import numpy as np
from scipy import stats
from scipy.spatial import distance
import copy
import pandas as pd
from sklearn import preprocessing
from sklearn import linear_model
from sklearn import cross_validation

def vox2MNI(vox, size):
    """
    Voxel coordinates transformed to MNI coordinates
    ------------------------------------------------
    Parameters:
        vox: voxel coordinates
        size: voxel size
    Return:
        MNI
    """
    MNI = np.empty(3)
    MNI[0] = (45 - vox[0])*size[0]
    MNI[1] = (vox[1] - 63)*size[1]
    MNI[2] = (vox[2] - 36)*size[2]
    return MNI

def MNI2vox(MNI, size):
    """
    MNI coordintes transformed to voxel coordinates
    ----------------------------------------------
    Parameters:
        MNI: MNI coordinates
        size: voxel size
    Return:
        vox
    """
    vox = np.empty(3)
    vox[0] = 45 - (MNI[0]/size[0])
    vox[1] = 63 + (MNI[1]/size[1])
    vox[2] = 36 + (MNI[2]/size[2])
    return vox

def caldice(data1, data2, label):
    """
    Compute dice coefficient
    ---------------------------------
    Parameters:
        data1, data2: matrix data with labels
                      data is 3 dimension
        label: class(region) labels
    Output:
        dice: dice values
    Example:
        >>> dice = caldice(data1, data2, [1,2,3,4])
    """
    if isinstance(label, list):
        label = np.array(label)
    dice = []
    for i in range(label.shape[0]):
        data_mul = (data1 == (i+1)) * (data2 == (i+1))
        data_sum = (data1 == (i+1)) + (data2 == (i+1))
        if not np.any(data_sum[data_sum!=0]):
            dice.append(np.nan)
        else:
            dice.append(2.0*np.sum(data_mul)/(np.sum(data1 == (i+1)) + np.sum(data2 == (i+1))))
    return dice

def caleta2(data1, data2, mask):
    """
    Compute eta2 between data1 and data2.
    eta2 = 1-sum((ai-mi)^2+(bi-mi)^2)/sum((ai-M)^2+(bi-M)^2)
    ai, value of each voxel in data1
    bi, value of each voxel in data2
    mi, 0.5*(ai+bi)
    M, average of sum(all signal voxels that have values)
    eta2 measures similarity between two images, note they need to comparable.
         higher eta2 means higher similarity between two images
    ------------------------------------------------------------------
    Parameters:
        data1: matrix data
        data2: matrix data
        mask: used to get inner-brain data
    Output:
        eta: eta2
    Example:
        >>> eta = caleta2(data1, data2, mask)
    """
    if isinstance(data1, list):
        data1 = np.array(data1)
    if isinstance(data2, list):
        data2 = np.array(data2)
    if data1.shape != data2.shape:
        raise Exception('data1 and data2 should have same shape!')
    data_avg1 = np.mean(data1[mask!=0])
    data_avg2 = np.mean(data2[mask!=0])
    M = 0.5*(data_avg1+data_avg2)
    sumwithin = 0
    sumtotal = 0
    flattendata1 = data1[mask!=0].flatten()
    flattendata2 = data2[mask!=0].flatten()
    for i in range(flattendata1.shape[0]):
        mi = (flattendata1[i] + flattendata2[i])/2
        sumwithin += (flattendata1[i]-mi)**2+(flattendata2[i]-mi)**2
        sumtotal += (flattendata1[i]-M)**2+(flattendata2[i]-M)**2
    eta = 1-float(sumwithin)/sumtotal
    return eta

def calcdist(u, v, metric = 'euclidean', p = 1):
    """
    Compute distance between u and v
    ----------------------------------
    Parameters:
        u: vector u
        v: vector v
        method: distance metric
                For concrete metric, please check scipy.spatial.distance.pdist
        p: p for 'minkowski' distance only.
    Return:
        dist: distance between vector u and vector v
    """
    if isinstance(u, list):
        u = np.array(u)
    if isinstance(v, list):
        v = np.array(v)
    vec = np.vstack((u, v))
    if metric == 'minkowski':
        dist = distance.pdist(vec, metric, p)
    else:
        dist = distance.pdist(vec, metric)
    return dist

def regressoutvariable(rawdata, covariate):
    """
    Regress out covariate variables from raw data
    -------------------------------------------------
    Parameters:
        rawdata: rawdata
        covariate: covariate to be regressed out
    Return:
        residue
    """
    if isinstance(rawdata, list):
        rawdata = np.array(rawdata)
    if isinstance(covariate, list):
        covariate = np.array(covariate)
    samp = ~np.isnan(rawdata * covariate)
    zfunc = lambda x: (x - np.nanmean(x))/np.nanstd(x)
    slope, intercept, r_value, p_value, std_err = stats.linregress(stats.zscore(rawdata[samp]), stats.zscore(covariate[samp]))
    residue = zfunc(rawdata) - slope*zfunc(covariate)
    return residue

def hemi_merge(left_region, right_region, meth = 'single', weight = None):
    """
    Merge hemisphere data
    -------------------------------------
    Parameters:
        left_region: feature data extracted from left hemisphere
        right_region: feature data extracted from right hemisphere
        meth: 'single' or 'both'.
          'single' means if no paired feature data in subjects, keep exist data
          'both' means if no paired feature data in subjects, delete these                subjects
        weight: weights for feature data.
            Note that it's a (nsubj x 2) matrix
            weight[:,0] means left_region
            weight[:,1] means right_region
    Return:
        merge_region 
    """
    if left_region.shape[0] != right_region.shape[0]:
        raise Exception('Subject numbers of left and right feature data should be equal')
    nsubj = left_region.shape[0]
    leftregion_used = np.copy(left_region)
    rightregion_used = np.copy(right_region)
    if weight is None:
        weight = np.ones((nsubj,2))
        weight[np.isnan(leftregion_used),0] = 0.0
        weight[np.isnan(rightregion_used),1] = 0.0 
    if meth == 'single': 
        leftregion_used[np.isnan(leftregion_used)] = 0.0
        rightregion_used[np.isnan(rightregion_used)] = 0.0
        merge_region = (leftregion_used*weight[:,0] + rightregion_used*weight[:,1])/(weight[:,0] + weight[:,1])
    elif meth == 'both':
        total_weight = weight[:,0] + weight[:,1]
        total_weight[total_weight<2] = 0.0
        merge_region = (left_region*weight[:,0] + right_region*weight[:,1])/total_weight
    else:
        raise Exception('meth will be ''both'' or ''single''')
    merge_region[merge_region == 0] = np.nan
    return merge_region

def removeoutlier(data, meth = None, thr = [-2,2]):
    """
    Remove data as outliers by indices you set
    -----------------------------
    Parameters:
        data: data you want to remove outlier
        meth: 'iqr' or 'std' or 'abs'
        thr: outlier standard threshold.
             For example, when meth == 'iqr' and thr == [-2,2],
             so data should in [-2*iqr, 2*iqr] to be left
    Return:
        residue_data: outlier values will be set as nan
        n_removed: outlier numbers
    """
    residue_data = copy.copy(data)   
    if meth is None:
        residue_data = data
        outlier_bool = np.zeros_like(residue_data, dtype=bool) 
    elif meth == 'abs':
        outlier_bool = ((data<thr[0])|(data>thr[1]))
        residue_data[((residue_data<thr[0])|(residue_data>thr[1]))] = np.nan
    elif meth == 'iqr':
        perc_thr = np.percentile(data, [25,75])
        f_iqr = perc_thr[1] - perc_thr[0]
        outlier_bool = ((data < perc_thr[0] + thr[0]*f_iqr)|(data >= perc_thr[1] + thr[1]*f_iqr))
        residue_data[outlier_bool] = np.nan
    elif meth == 'std':
        f_std = np.nanstd(data)
        f_mean = np.nanmean(data)
        outlier_bool = ((data<(f_mean+thr[0]*f_std))|(data>(f_mean+thr[1]*f_std)))
        residue_data[(residue_data<(f_mean+thr[0]*f_std))|(residue_data>(f_mean+thr[1]*f_std))] = np.nan
    else:
        raise Exception('method should be ''iqr'' or ''abs'' or ''std''')
    n_removed = sum(i for i in outlier_bool if i) 
    return n_removed, residue_data

def listwise_clean(data):
    """
    Clean missing data by listwise method
    Parameters:
        data: raw data
    Return: 
        clean_data: no missing data
    """
    if isinstance(data, list):
        data = np.array(data)
    clean_data = pd.DataFrame(data).dropna().values
    return clean_data    

def calwithincorr(meas, method = 'pearson'):
    """
    Compute correlation within matrix
    --------------------------------------
    Parameters:
        meas: nsubj x features
        method: 'pearson' or 'spearman'
                Do pearson correlation or spearman correlation
    Return:
        corrmatrix
        corrpval
    """
    if method == 'pearson':
        calfunc = stats.pearsonr
    elif method == 'spearman':
        calfunc = stats.spearmanr
    else:
        raise Exception('No such method now')
    corrmatrix = np.empty((meas.shape[1], meas.shape[1]))
    corrpval = np.empty((meas.shape[1], meas.shape[1]))
    for i in np.arange(meas.shape[1]):
        for j in np.arange(meas.shape[1]):
            corrmatrix[i, j], corrpval[i, j] = calfunc(meas[:,i], meas[:,j])
    return corrmatrix, corrpval

def get_masksize(mask):
    """
    Compute mask size
    -------------------------------------
    Parameters:
        mask: mask.
    Return:
        masksize: mask size of each roi
    """
    labels = np.unique(mask)[1:]
    if mask.ndim == 3:
        mask = np.expand_dims(mask, axis = 3)
    masksize = np.empty((mask.shape[3], labels.shape[0]))
    for i in range(mask.shape[3]):
        for j in range(labels.shape[0]):
            if np.any(mask[...,i] == labels[j]):
                masksize[i, j] = np.sum(mask[...,i] == labels[j])
            else:
                masksize[i, j] = np.nan
    return masksize
 
def get_signals(atlas, mask, method = 'mean', labelnum = None):
    """
    Extract roi signals of atlas
    --------------------------------------
    Parameters:
        atlas: atlas
        mask: masks. Different roi labelled differently
        method: 'mean', 'std', 'max', 'voxel', etc.
        labelnum: Mask's label numbers, by default is None. Add this parameters for group analysis
    Return:
        signals: nroi for activation data
                 resting signal x roi for resting data
    """
    labels = np.unique(mask)[1:]
    if labelnum is None:
        labelnum = np.max(labels)
    signals = []
    if method == 'mean':
        calfunc = np.nanmean
    elif method == 'std':
        calfunc = np.nanstd
    elif method == 'max':
        calfunc = np.max
    elif method == 'voxel':
        calfunc = np.array
    else:
        raise Exception('Method contains mean or std or peak')
    for i in range(labelnum):
        roisignal = atlas*(mask == (i+1))
        if np.any(roisignal):
            signals.append(roisignal[roisignal!=0])         
        else:
            signals.append(np.nan)
    # return signals    
    return [calfunc(sg) for sg in signals]

def get_coordinate(atlas, mask, size = [2,2,2], method = 'peak', labelnum = None):
    """
    Extract peak/center coordinate of rois
    --------------------------------------------
    Parameters:
        atlas: atlas
        mask: roi mask.
        size: voxel size
        method: 'peak' or 'center'
        labelnum: mask label numbers in total, by default is None, set parameters if you want to do group analysis
    Return:
        coordinates: nroi x 3 for activation data
                     Note that do not extract coordinate of resting data
    """
    labels = np.unique(mask)[1:]
    if labelnum is None:
        labelnum = np.max(labels)
    coordinate = np.empty((labelnum, 3))

    extractpeak = lambda x: np.unravel_index(x.argmax(), x.shape)
    extractcenter = lambda x: np.mean(np.transpose(np.nonzero(x)))

    if method == 'peak':
        calfunc = extractpeak
    elif method == 'center':
        calfunc = extractcenter
    else:
        raise Exception('Method contains peak or center')
    for i in range(labelnum):
        roisignal = atlas*(mask == (i+1))
        if np.any(roisignal):
            coordinate[i,:] = calfunc(roisignal)
            coordinate[i,:] = vox2MNI(coordinate[i,:], size)
        else:
            coordinate[i,:] = np.array([np.nan, np.nan, np.nan])
    return coordinate 

def get_specificroi(image, labellist):
    """
    Get specific roi from nifti image indiced by its label
    ----------------------------------------------------
    Parameters:
        image: nifti image data
        labellist: label you'd like to choose
    output:
        specific_data: data with extracted roi
    """
    logic_array = np.full(image.shape, False, dtype = bool)
    if isinstance(labellist, int):
        labellist = [labellist]
    for i,e in enumerate(labellist):
        logic_array += (image == e)
    specific_data = image*logic_array
    return specific_data
    
def lin_betafit(estimator, X, y, c, tail = 'both'):
    """
    Linear estimation using linear models
    -----------------------------------------
    Parameters:
        estimator: linear model estimator
        X: Independent matrix
        y: Dependent matrix
        c: contrast
        tail: significance tails
    Return:
        r2: determined values
        beta: slopes (scaled beta)
        t: tvals
        tpval: significance of beta
        f: f values of model test
        fpval: p values of f test 
    """
    if isinstance(c, list):
        c = np.array(c)
    if c.ndim == 1:
        c = np.expand_dims(c, axis = 1)
    if X.ndim == 1:
        X = np.expand_dims(X, axis = 1)
    if y.ndim == 1:
        y = np.expand_dims(y, axis = 1)
    X = preprocessing.scale(X)
    y = preprocessing.scale(y)
    nsubj = X.shape[0]
    estimator.fit(X,y)
    beta = estimator.coef_.T
    y_est = estimator.predict(X)
    err = y - y_est
    errvar = (np.dot(err.T, err))/(nsubj - X.shape[1])
    t = np.dot(c.T, beta)/np.sqrt(np.dot(np.dot(c.T, np.linalg.inv(np.dot(X.T, X))),np.dot(c,errvar)))
    r2 = estimator.score(X,y)
    f = (r2/(X.shape[1]-1))/((1-r2)/(nsubj-X.shape[1]))
    if tail == 'both':
        tpval = stats.t.sf(np.abs(t), nsubj-X.shape[1])*2
        fpval = stats.f.sf(np.abs(f), X.shape[1]-1, nsubj-X.shape[1])*2
    elif tail == 'single':
        tpval = stats.t.sf(np.abs(t), nsubj-X.shape[1])
        fpval = stats.f.sf(np.abs(f), X.shape[1]-1, nsubj-X.shape[1])
    else:
        raise Exception('wrong pointed tail.')
    return r2, beta[:,0], t, tpval, f, fpval

def permutation_cross_validation(estimator, X, y, n_fold=3, isshuffle = True, cvmeth = 'shufflesplit', score_type = 'r2', n_perm = 1000):
    """
    An easy way to evaluate the significance of a cross-validated score by permutations
    -------------------------------------------------
    Parameters:
        estimator: linear model estimator
        X: IV
        y: DV
        n_fold: fold number cross validation
        cvmeth: kfold or shufflesplit. 
                shufflesplit is the random permutation cross-validation iterator
        score_type: scoring type, 'r2' as default
        n_perm: permutation numbers
    Return:
        score: model scores
        permutation_scores: model scores when permutation labels
        pvalues: p value of permutation scores
    """
    if X.ndim == 1:
        X = np.expand_dims(X, axis = 1)
    if y.ndim == 1:
        y = np.expand_dims(y, axis = 1)
    X = preprocessing.scale(X)
    y = preprocessing.scale(y)
    if cvmeth == 'kfold':
        cvmethod = cross_validation.KFold(y.shape[0], n_fold, shuffle = isshuffle)
    elif cvmeth == 'shufflesplit':
        testsize = 1.0/n_fold
        cvmethod = cross_validation.ShuffleSplit(y.shape[0], n_iter = 100, test_size = testsize, random_state = 0)
    score, permutation_scores, pvalues = cross_validation.permutation_test_score(estimator, X, y, scoring = score_type, cv = cvmethod, n_permutations = n_perm)
    return score, permutation_scores, pvalues

         










