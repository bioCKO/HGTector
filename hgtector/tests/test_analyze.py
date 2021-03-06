#!/usr/bin/env python3

# ----------------------------------------------------------------------------
# Copyright (c) 2013--, Qiyun Zhu and Katharina Dittmar.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

from unittest import TestCase, main
from os import remove
from os.path import join, isfile, dirname, realpath
from shutil import rmtree
from tempfile import mkdtemp

import numpy as np
import pandas as pd

from sklearn.neighbors import KernelDensity

from hgtector.analyze import Analyze
from hgtector.util import add_children, get_descendants


class AnalyzeTests(TestCase):
    def setUp(self):
        self.tmpdir = mkdtemp()
        self.datadir = join(dirname(realpath(__file__)), 'data')

        np.random.seed(42)
        self.dist_norm1 = np.random.normal(5.0, 2.0, 1500)
        self.dist_norm2 = np.random.normal(1.0, 0.5, 500)
        self.dist_lognorm = np.random.lognormal(0.0, 1.0, 1000)
        self.dist_gamma = np.random.gamma(2, 2, 800)

    def tearDown(self):
        rmtree(self.tmpdir)

    def test___call__(self):
        # TODO
        pass

    def test_set_parameters(self):
        # TODO
        pass

    def test_read_input(self):
        # TODO
        pass

    def test_read_search_results(self):
        file = join(self.datadir, 'DnaK', 'search', 'sample.tsv')
        obs = Analyze.read_search_results(file)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]['id'], 'WP_000516135.1')
        self.assertAlmostEqual(obs[0]['score'], 1092.8)
        self.assertTupleEqual(obs[0]['hits'].shape, (12, 5))
        self.assertEqual(obs[0]['hits'].iloc[2].name, 'NP_454622.1')
        self.assertAlmostEqual(obs[0]['hits']['evalue']['NP_230502.1'],
                               5.9e-282)
        self.assertEqual(obs[0]['hits']['taxid']['NP_384288.1'], '266834')

        # maximum number of hits
        obs = Analyze.read_search_results(file, 5)
        self.assertEqual(len(obs[0]['hits']), 5)

    def test_assign_taxonomy(self):
        # TODO
        pass

    def test_infer_genome_tax(self):
        taxdump = _taxdump_from_text(taxdump_proteo)

        # five proteins, in which four have hits
        taxids = [['562', '620', '570'],  # E. coli
                  ['562', '585056', '1038927', '2'],  # E. coli
                  ['561', '543', '776'],  # Escherichia
                  ['548', '570', '1236'],  # K. aerogenes
                  []]
        prots = [{'hits': pd.DataFrame(x, columns=['taxid'])} for x in taxids]
        obs = Analyze.infer_genome_tax(prots, taxdump, 75)
        exp = ('561', 75.0)  # 3 / 4 best hits assigned to Escherichia
        self.assertTupleEqual(obs, exp)

        # reduce coverage threshold
        obs = Analyze.infer_genome_tax(prots, taxdump, 50)
        exp = ('562', 50.0)  # 2 / 4 best hits assigned to Escherichia
        self.assertTupleEqual(obs, exp)

        # remove one protein that best matches E. coli
        prots.pop(0)
        obs = Analyze.infer_genome_tax(prots, taxdump, 75)
        exp = ('543', 100.0)  # 3 / 3 best hits assigned to Enterobacteriaceae
        self.assertTupleEqual(obs, exp)

    def test_sum_taxids(self):
        # TODO
        pass

    def test_define_groups(self):
        me = Analyze()
        me.taxdump = _taxdump_from_text(taxdump_proteo)
        add_children(me.taxdump)
        me.groups = {}

        # user defined groups:
        # self: genera Escherichia and Shigella
        # close: family Enterobacteriaceae
        me.self_tax = '561,620'
        me.close_tax = '543'
        me.define_groups()
        self.assertListEqual(me.self_tax, ['561', '620'])
        exp = {'561', '562', '585056', '1038927', '2580236', '620', '622'}
        self.assertSetEqual(me.groups['self'], exp)
        self.assertListEqual(me.close_tax, ['543'])
        exp = {'543', '548', '570'}
        self.assertSetEqual(me.groups['close'], exp)

    def test_infer_self_group(self):
        me = Analyze()
        me.taxdump = _taxdump_from_text(taxdump_proteo)
        add_children(me.taxdump)

        # assign to LCA of all genomes (E. coli)
        me.self_tax = None
        me.lca = '562'
        me.self_rank = None
        me.infer_self_group()
        self.assertListEqual(me.self_tax, ['562'])

        # raise LCA to genus level (Escherichia)
        me.self_tax = None
        me.lca = '562'
        me.self_rank = 'genus'
        me.infer_self_group()
        self.assertListEqual(me.self_tax, ['561'])

        # LCA (Enterobacteriaceae) is already above designated rank (genus)
        me.self_tax = None
        me.lca = '543'
        me.self_rank = 'genus'
        me.infer_self_group()
        self.assertListEqual(me.self_tax, ['543'])

    def test_infer_close_group(self):
        me = Analyze()
        me.taxdump = _taxdump_from_text(taxdump_proteo)
        add_children(me.taxdump)
        me.groups = {}

        # close group is parent of LCA of self group
        me.self_tax = ['562']  # E. coli
        me.groups['self'] = set(['562'] + get_descendants('562', me.taxdump))
        me.close_tax = None
        me.close_size = None
        me.infer_close_group()
        self.assertListEqual(me.close_tax, ['561'])  # Escherichia
        self.assertSetEqual(me.groups['close'], {'561', '2580236'})

        # close group must have at least 5 taxa
        me.close_tax = None
        me.groups['close'] = None
        me.close_size = 5
        me.infer_close_group()
        self.assertListEqual(me.close_tax, ['543'])  # Enterobacteriaceae
        exp = {'543', '620', '622', '570', '548', '561', '2580236'}
        self.assertSetEqual(me.groups['close'], exp)

        # close group is LCA of multiple self groups
        me.self_tax = ['561', '620']  # Escherichia and Shigella
        me.groups['self'] = set().union(*[[x] + get_descendants(
            x, me.taxdump) for x in me.self_tax])
        me.close_tax = None
        me.groups['close'] = None
        me.close_size = None
        me.infer_close_group()
        self.assertListEqual(me.close_tax, ['543'])  # Enterobacteriaceae
        exp = {'543', '570', '548'}
        self.assertSetEqual(me.groups['close'], exp)

    def test_calc_scores(self):
        # TODO
        pass

    def test_find_match(self):
        me = Analyze()
        me.taxdump = _taxdump_from_text(taxdump_proteo)
        add_children(me.taxdump)
        df = pd.DataFrame(
            [[100, '585056'],  # E. coli UMN026
             [99, '1038927'],  # E. coli O104:H4
             [97, '562'],      # Escherichia coli
             [95, '622'],      # Shigella dysenteriae
             [92, '543'],      # Enterobacteriaceae
             [88, '548'],      # Klebsiella aerogenes
             [80, '766']],     # Rickettsiales
            columns=['score', 'taxid'])

        # keep top 1% hits
        me.match_th = 0.99
        self.assertEqual(me.find_match(df), '562')

        # keep top 10% hits
        me.match_th = 0.9
        self.assertEqual(me.find_match(df), '543')

        # keep top 20% hits
        me.match_th = 0.8
        self.assertEqual(me.find_match(df), '1224')

        # input DataFrame is empty
        self.assertEqual(me.find_match(pd.DataFrame()), '0')

    def test_make_score_table(self):
        # TODO
        pass

    def test_remove_orphans(self):
        me = Analyze()
        me.df = pd.DataFrame([
            [1.0, 0.2], [0.5, 0.4], [0.0, 0.0], [0.8, 0.0], [0.0, 0.7]],
            columns=['close', 'distal'])
        me.remove_orphans()
        self.assertListEqual(me.df.values.tolist(), [
            [1.0, 0.2], [0.5, 0.4], [0.8, 0.0], [0.0, 0.7]])

    def test_remove_outliers(self):
        me = Analyze()
        me.self_low = False
        df = pd.DataFrame(np.array([self.dist_gamma,
                                    self.dist_lognorm[:800]]).T,
                          columns=['close', 'distal'])

        # Z-score
        me.df = df.copy()
        me.outliers = 'zscore'
        me.remove_outliers()
        self.assertEqual(me.df.shape[0], 781)

        # boxplot
        me.df = df.copy()
        me.outliers = 'boxplot'
        me.remove_outliers()
        self.assertEqual(me.df.shape[0], 710)

    def test_relevant_groups(self):
        me = Analyze()
        me.self_low = False
        self.assertListEqual(me.relevant_groups(), ['close', 'distal'])
        me.self_low = True
        self.assertListEqual(me.relevant_groups(), ['self', 'close', 'distal'])

    def test_outliers_zscore(self):
        df = pd.DataFrame(np.array([self.dist_gamma,
                                    self.dist_lognorm[:800]]).T,
                          columns=['close', 'distal'])
        obs = Analyze.outliers_zscore(df, ['close', 'distal'])
        self.assertEqual(obs.shape[0], 781)

    def test_outliers_boxplot(self):
        df = pd.DataFrame(np.array([self.dist_gamma,
                                    self.dist_lognorm[:800]]).T,
                          columns=['close', 'distal'])
        obs = Analyze.outliers_boxplot(df, ['close', 'distal'])
        self.assertEqual(obs.shape[0], 710)

    def test_predict_hgt(self):
        # TODO
        pass

    def test_cluster_kde(self):
        me = Analyze()
        data = np.concatenate([self.dist_norm1, self.dist_norm2])
        me.df = pd.Series(data, name='group').to_frame()
        me.bw_steps = 10
        me.noise = 50
        me.low_part = 75
        me.output = self.tmpdir

        # grid search
        me.bandwidth = 'grid'
        obs = me.cluster_kde('group')
        self.assertAlmostEqual(obs, 1.855525575742988)

        # Silverman's rule-of-thumb
        me.bandwidth = 'silverman'
        obs = me.cluster_kde('group')
        self.assertAlmostEqual(obs, 2.2279977615745703)

        # fixed value
        me.bandwidth = 0.5
        obs = me.cluster_kde('group')
        self.assertAlmostEqual(obs, 2.2507008281395433)

        # smart KDE
        me.bandwidth = 'auto'
        obs = me.cluster_kde('group')
        self.assertAlmostEqual(obs, 2.1903958075763343)

        # clean up
        remove(join(self.tmpdir, 'group.kde.png'))

    def test_perform_kde(self):
        me = Analyze()
        me.bw_steps = 10
        data = np.concatenate([self.dist_norm1, self.dist_norm2])

        # grid search
        me.bandwidth = 'grid'
        obs = me.perform_kde(data)[2]
        self.assertAlmostEqual(obs, 0.21544346900318834)

        # Silverman's rule-of-thumb
        me.bandwidth = 'silverman'
        obs = me.perform_kde(data)[2]
        self.assertAlmostEqual(obs, 0.48713295460585126)

        # fixed value
        me.bandwidth = 0.5
        obs = me.perform_kde(data)[2]
        self.assertAlmostEqual(obs, 0.5)

    def test_grid_kde(self):
        estimator = KernelDensity(kernel='gaussian')

        # unimodal
        data = self.dist_gamma[:, np.newaxis]
        obs = Analyze.grid_kde(data, estimator, 10).bandwidth
        self.assertAlmostEqual(obs, 0.774263682681127)

        # bimodal
        data = np.concatenate([
            self.dist_norm1, self.dist_norm2])[:, np.newaxis]
        obs = Analyze.grid_kde(data, estimator, 10).bandwidth
        self.assertAlmostEqual(obs, 0.46415888336127786)

        data = np.array([1, 2, 3, 4, 5])[:, np.newaxis]
        obs = Analyze.grid_kde(data, estimator, 5).bandwidth
        self.assertAlmostEqual(obs, 1.0)

        # very few data points (bw = high end)
        data = np.array([1, 2, 3, 4, 5])[:, np.newaxis]
        obs = Analyze.grid_kde(data, estimator, 5).bandwidth
        self.assertAlmostEqual(obs, 1.0)

        # constant values (bw = low end)
        data = np.array([1, 1, 1, 1, 1])[:, np.newaxis]
        obs = Analyze.grid_kde(data, estimator, 5).bandwidth
        self.assertAlmostEqual(obs, 0.1)

        # too few data points (less than splits)
        data = np.array([1, 2, 3])[:, np.newaxis]
        with self.assertRaises(ValueError) as ctx:
            Analyze.grid_kde(data, estimator, 5)
        msg = 'Cannot perform grid search on 3 data point(s).'
        self.assertEqual(str(ctx.exception), msg)

    def test_silverman_bw(self):
        # unimodal
        obs = Analyze.silverman_bw(self.dist_gamma)
        self.assertAlmostEqual(obs, 0.6148288686346546)
        obs = Analyze.silverman_bw(self.dist_lognorm)
        self.assertAlmostEqual(obs, 0.2384666552244172)

        # bimodal
        obs = Analyze.silverman_bw(np.concatenate([
            self.dist_norm1, self.dist_norm2]))
        self.assertAlmostEqual(obs, 0.48713295460585126)

        # constant values
        obs = Analyze.silverman_bw([1, 1, 1, 1, 1])
        self.assertAlmostEqual(obs, 0.652301697309926)

        # one element
        with self.assertRaises(ValueError) as ctx:
            Analyze.silverman_bw([5])
        msg = 'Cannot calculate bandwidth on 1 data point.'
        self.assertEqual(str(ctx.exception), msg)

    def test_density_func(self):
        data = self.dist_norm1[:, np.newaxis]
        estimator = KernelDensity(kernel='gaussian', bandwidth=0.5)
        kde = estimator.fit(data)
        obs = Analyze.density_func(data, kde, 10)
        exp = (np.array([-1.48253468, 0.0939095, 1.67035369, 3.24679787,
                         4.82324206, 6.39968624, 7.97613043, 9.55257461,
                         11.1290188, 12.70546298]),
               np.array([0.00104342, 0.00788705, 0.0496806, 0.13173376,
                         0.19176352, 0.15754466, 0.06992292, 0.02140856,
                         0.00150463, 0.00053637]))
        np.testing.assert_array_almost_equal(obs, exp)

    def test_first_hill(self):
        # typical bimodal distribution
        data = np.concatenate([
            self.dist_norm1, self.dist_norm2])[:, np.newaxis]
        estimator = KernelDensity(kernel='gaussian', bandwidth=0.5)
        kde = estimator.fit(data)
        x, y = Analyze.density_func(data, kde, 100)
        obs_x, obs_y = Analyze.first_hill(x, y)
        exp_x, exp_y = 1.0971012583068704, 2.5302323352207674
        self.assertAlmostEqual(obs_x, exp_x)
        self.assertAlmostEqual(obs_y, exp_y)

        # peak larger than valley
        data = np.negative(data)
        kde = estimator.fit(data)
        x, y = Analyze.density_func(data, kde, 100)
        with self.assertRaises(ValueError) as ctx:
            Analyze.first_hill(x, y)
        msg = 'Peak is larger than valley.'
        self.assertEqual(str(ctx.exception), msg)

        # unimodal distribution
        data = self.dist_norm1[:, np.newaxis]
        kde = estimator.fit(data)
        x, y = Analyze.density_func(data, kde, 100)
        with self.assertRaises(ValueError) as ctx:
            Analyze.first_hill(x, y)
        msg = 'Cannot identify at least two peaks.'
        self.assertEqual(str(ctx.exception), msg)

    def test_plot_hist(self):
        fp = join(self.tmpdir, 'tmp.png')
        Analyze.plot_hist(self.dist_gamma, fp)
        self.assertTrue(isfile(fp))
        remove(fp)

    def test_plot_density(self):
        data = np.concatenate([
            self.dist_norm1, self.dist_norm2])[:, np.newaxis]
        estimator = KernelDensity(kernel='gaussian', bandwidth=0.5)
        kde = estimator.fit(data)
        x, y = Analyze.density_func(data, kde, 100)
        peak, valley = Analyze.first_hill(x, y)
        th = valley - (valley - peak) * 0.5 / 100
        fp = join(self.tmpdir, 'tmp.png')
        Analyze.plot_density(x, y, peak, valley, th, fp)
        self.assertTrue(isfile(fp))
        remove(fp)

    def test_smart_kde(self):
        me = Analyze()
        data = np.concatenate([self.dist_norm1, self.dist_norm2])
        me.df = pd.Series(data, name='group').to_frame()
        me.bw_steps = 10
        me.noise = 50
        me.low_part = 75
        me.output = self.tmpdir
        obs = me.smart_kde('group')
        self.assertAlmostEqual(obs, 2.1903958075763343)
        file = join(self.tmpdir, 'group.kde.png')
        self.assertTrue(isfile(file))
        remove(file)

    def test_calc_cluster_props(self):
        me = Analyze()
        me.self_low = False
        me.df = pd.DataFrame(np.array(
            [self.dist_gamma, self.dist_lognorm[:800]]).T,
            columns=['close', 'distal'])
        me.df['hgt'] = (me.df['close'] < 2) & (me.df['distal'] > 2)
        obs = me.calc_cluster_props()
        self.assertAlmostEqual(obs[0], 1.094658052928843)
        self.assertAlmostEqual(obs[1], 4.30076698399293)
        obs = me.df['silh'].describe()
        self.assertAlmostEqual(obs['mean'], 0.312495082044277)
        self.assertAlmostEqual(obs['std'], 0.21945541659155993)
        self.assertEqual(me.df.query('hgt & silh < 0.5').shape[0], 35)

    def test_refine_cluster(self):
        me = Analyze()
        me.self_low = False
        me.silhouette = 0.5
        me.df = pd.DataFrame(np.array(
            [self.dist_gamma, self.dist_lognorm[:800]]).T,
            columns=['close', 'distal'])
        me.df['hgt'] = (me.df['close'] < 2) & (me.df['distal'] > 2)
        me.refine_cluster(me.calc_cluster_props())
        self.assertEqual(me.df[me.df['hgt']].shape[0], 11)

    def test_plot_hgts(self):
        me = Analyze()
        me.output = self.tmpdir
        me.df = pd.DataFrame(np.array(
            [self.dist_gamma, self.dist_lognorm[:800]]).T,
            columns=['close', 'distal'])
        me.df['hgt'] = (me.df['close'] < 2) & (me.df['distal'] > 2)
        me.plot_hgts()
        fp = join(self.tmpdir, 'scatter.png')
        self.assertTrue(isfile(fp))
        remove(fp)


"""Constants"""

taxdump_proteo = (
    '1,root,1,no rank',
    '131567,cellular organisms,1,no rank',
    '2,Bacteria,131567,superkingdom',
    '1224,Proteobacteria,2,phylum',
    '28211,Alphaproteobacteria,1224,class',
    '766,Rickettsiales,28211,order',
    '1236,Gammaproteobacteria,1224,class',
    '91347,Enterobacterales,1236,order',
    '543,Enterobacteriaceae,91347,family',
    '561,Escherichia,543,genus',
    '562,Escherichia coli,561,species',
    '585056,Escherichia coli UMN026,562,no rank',
    '1038927,Escherichia coli O104:H4,562,no rank',
    '2580236,synthetic Escherichia coli Syn61,561,species',
    '620,Shigella,543,genus',
    '622,Shigella dysenteriae,620,species',
    '570,Klebsiella,543,genus',
    '548,Klebsiella aerogenes,570,species',
    '118884,unclassified Gammaproteobacteria,1236,no rank',
    '126792,Plasmid pPY113,1,species')


"""Helpers"""


def _taxdump_from_text(text):
    """Read taxdump from text.

    Parameters
    ----------
    text : list of str
        multi-line, tab-delimited text

    Returns
    -------
    dict of dict
        taxonomy database
    """
    res = {}
    for line in text:
        x = line.split(',')
        res[x[0]] = {'name': x[1], 'parent': x[2], 'rank': x[3]}
    return res


if __name__ == '__main__':
    main()
