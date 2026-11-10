#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GMMClassifier —— 每类一个高斯混合模型的似然判别分类器。

独立成模块的原因：训练脚本以 __main__ 运行时，joblib 会把类的 pickle
引用写成 __main__.GMMClassifier；Flask 等其他进程反序列化时 __main__
里没有这个类，会报 "module '__main__' has no attribute 'GMMClassifier'"。
放在稳定可导入的模块下，训练/推理两端都 `from gmm_classifier import
GMMClassifier` 即可（scripts/ 需在 sys.path 中）。

接口与 sklearn 分类器一致：fit / predict / predict_proba / classes_。
"""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.mixture import GaussianMixture

RANDOM_STATE = 42


class GMMClassifier(BaseEstimator, ClassifierMixin):
    """每类一个 GMM，按对数似然判类；predict_proba 用 softmax 归一化"""

    def __init__(self, n_components=4, random_state=RANDOM_STATE):
        self.n_components = n_components
        self.random_state = random_state

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        self.gmms_ = {}
        for c in self.classes_:
            Xc = X[y == c]
            n_comp = min(self.n_components, max(1, len(Xc)))
            gmm = GaussianMixture(
                n_components=n_comp, covariance_type='full',
                random_state=self.random_state, reg_covar=1e-3)
            gmm.fit(Xc)
            self.gmms_[c] = gmm
        return self

    def _log_likelihood(self, X):
        ll = np.zeros((X.shape[0], len(self.classes_)))
        for i, c in enumerate(self.classes_):
            ll[:, i] = self.gmms_[c].score_samples(X)
        return ll

    def predict(self, X):
        return self.classes_[np.argmax(self._log_likelihood(X), axis=1)]

    def predict_proba(self, X):
        ll = self._log_likelihood(X)
        ll_shift = ll - ll.max(axis=1, keepdims=True)
        proba = np.exp(ll_shift)
        proba /= proba.sum(axis=1, keepdims=True)
        return proba
