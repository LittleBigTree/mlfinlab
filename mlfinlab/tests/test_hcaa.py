"""
Tests the different portfolio optimisation algorithms
"""

import unittest
import os
import numpy as np
import pandas as pd
from mlfinlab.portfolio_optimization.hcaa import HierarchicalClusteringAssetAllocation
from mlfinlab.portfolio_optimization.returns_estimators import ReturnsEstimators


class TestHCAA(unittest.TestCase):
    # pylint: disable=too-many-public-methods
    """
    Tests different functions of the HCAA algorithm class.
    """

    def setUp(self):
        """
        Set the file path for the tick data csv
        """
        project_path = os.path.dirname(__file__)
        data_path = project_path + '/test_data/stock_prices.csv'
        self.data = pd.read_csv(data_path, parse_dates=True, index_col="Date")

    def test_hcaa_equal_weight(self):
        """
        Test the weights calculated by the HCAA algorithm - if all the weights are positive and
        their sum is equal to 1.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data,
                      asset_names=self.data.columns,
                      optimal_num_clusters=5,
                      risk_measure='equal_weighting')
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_hcaa_min_variance(self):
        """
        Test the weights calculated by the HCAA algorithm - if all the weights are positive and
        their sum is equal to 1.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data,
                      asset_names=self.data.columns,
                      optimal_num_clusters=5,
                      risk_measure='variance')
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_hcaa_min_standard_deviation(self):
        """
        Test the weights calculated by the HCAA algorithm - if all the weights are positive and
        their sum is equal to 1.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data,
                      asset_names=self.data.columns,
                      optimal_num_clusters=4,
                      risk_measure='standard_deviation')
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_value_error_for_expected_shortfall(self):
        """
        Test ValueError when expected_shortfall is the allocation metric, no asset_returns dataframe
        is given and no asset_prices dataframe is passed.
        """

        with self.assertRaises(ValueError):
            hcaa = HierarchicalClusteringAssetAllocation()
            hcaa.allocate(asset_names=self.data.columns,
                          optimal_num_clusters=5,
                          risk_measure='expected_shortfall')

    def test_hcaa_expected_shortfall(self):
        """
        Test the weights calculated by the HCAA algorithm - if all the weights are positive and
        their sum is equal to 1.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data,
                      asset_names=self.data.columns,
                      optimal_num_clusters=5,
                      risk_measure='expected_shortfall')
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_hcaa_conditional_drawdown_risk(self):
        """
        Test the weights calculated by the HCAA algorithm - if all the weights are positive and
        their sum is equal to 1.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data,
                      asset_names=self.data.columns,
                      optimal_num_clusters=5,
                      risk_measure='conditional_drawdown_risk')
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_quasi_diagnalization(self):
        """
        Test the quasi-diagnalisation step of HCAA algorithm.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data,
                      linkage='single',
                      optimal_num_clusters=5,
                      asset_names=self.data.columns)
        assert hcaa.ordered_indices == [13, 9, 10, 8, 14, 7, 1, 6, 4, 16, 3, 17,
                                        12, 18, 22, 0, 15, 21, 11, 2, 20, 5, 19]

    def test_value_error_for_non_dataframe_input(self):
        """
        Test ValueError on passing non-dataframe input.
        """

        with self.assertRaises(ValueError):
            hcaa = HierarchicalClusteringAssetAllocation()
            hcaa.allocate(asset_prices=self.data.values, asset_names=self.data.columns)

    def test_value_error_for_non_date_index(self):
        """
        Test ValueError on passing dataframe not indexed by date.
        """

        with self.assertRaises(ValueError):
            hcaa = HierarchicalClusteringAssetAllocation()
            data = self.data.reset_index()
            hcaa.allocate(asset_prices=data, asset_names=self.data.columns)

    def test_all_inputs_none(self):
        """
        Test allocation when all inputs are None.
        """

        with self.assertRaises(ValueError):
            hcaa = HierarchicalClusteringAssetAllocation()
            hcaa.allocate(asset_names=self.data.columns)

    def test_hcaa_with_input_as_returns(self):
        """
        Test HCAA when passing asset returns dataframe as input.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        returns = ReturnsEstimators().calculate_returns(asset_prices=self.data)
        hcaa.allocate(asset_returns=returns, asset_names=self.data.columns)
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_hcaa_with_asset_returns_as_none(self):
        """
        Test HCAA when asset returns are not required for calculating the weights.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        returns = ReturnsEstimators().calculate_returns(asset_prices=self.data)
        hcaa.allocate(asset_names=self.data.columns,
                      covariance_matrix=returns.cov(),
                      optimal_num_clusters=5,
                      risk_measure='equal_weighting')
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_hcaa_with_input_as_covariance_matrix(self):
        """
        Test HCAA when passing a covariance matrix as input.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        returns = ReturnsEstimators().calculate_returns(asset_prices=self.data)
        hcaa.allocate(asset_names=self.data.columns,
                      covariance_matrix=returns.cov(),
                      optimal_num_clusters=6,
                      asset_returns=returns)
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_value_error_for_risk_measure(self):
        """
        Test HCAA when a different allocation metric string is used.
        """

        with self.assertRaises(ValueError):
            hcaa = HierarchicalClusteringAssetAllocation()
            hcaa.allocate(asset_names=self.data.columns, asset_prices=self.data, risk_measure='random_metric')

    def test_no_asset_names(self):
        """
        Test HCAA when not supplying a list of asset names.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data,
                      optimal_num_clusters=6)
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_no_asset_names_with_asset_returns(self):
        """
        Test HCAA when not supplying a list of asset names and when the user passes asset_returns.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        returns = ReturnsEstimators().calculate_returns(asset_prices=self.data)
        hcaa.allocate(asset_returns=returns,
                      optimal_num_clusters=6)
        weights = hcaa.weights.values[0]
        assert (weights >= 0).all()
        assert len(weights) == self.data.shape[1]
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_value_error_with_no_asset_names(self):
        """
        Test ValueError when not supplying a list of asset names and no other input
        """

        with self.assertRaises(ValueError):
            hcaa = HierarchicalClusteringAssetAllocation()
            returns = ReturnsEstimators().calculate_returns(asset_prices=self.data)
            hcaa.allocate(asset_returns=returns.values,
                          optimal_num_clusters=6)

    def test_dendrogram_plot(self):
        """
        Test if dendrogram plot object is correctly rendered.
        """

        hcaa = HierarchicalClusteringAssetAllocation()
        hcaa.allocate(asset_prices=self.data, optimal_num_clusters=5)
        dendrogram = hcaa.plot_clusters(assets=self.data.columns)
        assert dendrogram.get('icoord')
        assert dendrogram.get('dcoord')
        assert dendrogram.get('ivl')
        assert dendrogram.get('leaves')
        assert dendrogram.get('color_list')
