"""
A base class for the various bar types. Includes the logic shared between classes, to minimise the amount of
duplicated code.
"""

from abc import ABC, abstractmethod

import pandas as pd
import numpy as np
from mlfinlab.util.fast_ewma import ewma


class BaseBars(ABC):
    """
    Abstract base class which contains the structure which is shared between the various standard and information
    driven bars. There are some methods contained in here that would only be applicable to information bars but
    they are included here so as to avoid a complicated nested class structure.
    """

    def __init__(self, file_path_or_df, metric, batch_size=2e7):
        """
        Constructor

        :param file_path_or_df: (String) Path to the csv file containing raw tick data in the format[date_time, price, volume]
        :param metric: (String) type of imbalance bar to create. Example: dollar_imbalance.
        :param batch_size: (Int) Number of rows to read in from the csv, per batch.
        """

        if isinstance(file_path_or_df, str):
            self.generator_object = pd.read_csv(file_path_or_df, chunksize=batch_size)
            # Read in the first row & assert format
            first_row = pd.read_csv(file_path_or_df, nrows=1)
            self._assert_csv(first_row)
        elif isinstance(file_path_or_df, pd.DataFrame):
            self.generator_object = self._crop_data_frame_in_batches(file_path_or_df, batch_size)
            first_row = file_path_or_df.iloc[0]
            self._assert_csv(first_row)
        else:
            raise ValueError('file_path_or_df is neither string(path to a csv file) nor pd.DataFrame')

        # Base properties
        self.metric = metric
        self.prev_tick_rule = 0

        # Cache properties
        self.open_price, self.prev_price = None, None
        self.high_price, self.low_price = -np.inf, np.inf
        self.cum_statistics = {'cum_ticks': 0, 'cum_dollar_value': 0, 'cum_volume': 0, 'cum_buy_volume': 0}

        # Batch_run properties
        self.flag = False  # The first flag is false since the first batch doesn't use the cache

    def _crop_data_frame_in_batches(self, df, chunksize):
        """
        Splits df into chunks of chunksize
        :param df: (pd.DataFrame) to split
        :param chunksize: (Int) number of rows in chunk
        :return: (list) of chunks (pd.DataFrames)
        """
        generator_object = []
        for _, chunk in df.groupby(np.arange(len(df)) // chunksize):
            generator_object.append(chunk)
        return generator_object

    def batch_run(self, verbose=True, to_csv=False, output_path=None):
        """
        Reads a csv file in batches and then constructs the financial data structure in the form of a DataFrame.
        The csv file must have only 3 columns: date_time, price, & volume.
        :param verbose: (Boolean) Flag whether to print message on each processed batch or not
        :param to_csv: (Boolean) Flag for writing the results of bars generation to local csv file, or to in-memory DataFrame
        :param output_path: (Boolean) Path to results file, if to_csv = True

        :return: (DataFrame or None) Financial data structure
        """

        if to_csv is True:
            header = True  # if to_csv is True, header should written on the first batch only
            open(output_path, 'w').close()  # clean output csv file

        if verbose:  # pragma: no cover
            print('Reading data in batches:')

        # Read csv in batches
        count = 0
        final_bars = []
        cols = ['date_time', 'open', 'high', 'low', 'close', 'volume', 'cum_buy_volume', 'cum_ticks',
                'cum_dollar_value']
        for batch in self.generator_object:
            if verbose:  # pragma: no cover
                print('Batch number:', count)

            list_bars = self._extract_bars(data=batch)

            if to_csv is True:
                pd.DataFrame(list_bars, columns=cols).to_csv(output_path, header=header, index=False, mode='a')
                header = False
            else:
                # Append to bars list
                final_bars += list_bars
            count += 1

            # Set flag to True: notify function to use cache
            self.flag = True

        if verbose:  # pragma: no cover
            print('Returning bars \n')

        # Return a DataFrame
        if final_bars:
            bars_df = pd.DataFrame(final_bars, columns=cols)
            return bars_df

        # Processed DataFrame is stored in .csv file, return None
        return None

    @abstractmethod
    def _extract_bars(self, data):
        """
        This method is required by all the bar types and is used to create the desired bars.
        :param data: (DataFrame) Contains 3 columns - date_time, price, and volume.
        :return: (List) of bars built using the current batch.
        """

    @abstractmethod
    def _reset_cache(self):
        """
        This method is required by all the bar types. It describes how cache should be reset
        when new bar is sampled
        """

    @staticmethod
    def _assert_csv(test_batch):
        """
        Tests that the csv file read has the format: date_time, price, and volume.
        If not then the user needs to create such a file. This format is in place to remove any unwanted overhead.

        :param test_batch: (DataFrame) the first row of the dataset.
        """
        assert test_batch.shape[1] == 3, 'Must have only 3 columns in csv: date_time, price, & volume.'
        assert isinstance(test_batch.iloc[0, 1], float), 'price column in csv not float.'
        assert not isinstance(test_batch.iloc[0, 2], str), 'volume column in csv not int or float.'

        try:
            pd.to_datetime(test_batch.iloc[0, 0])
        except ValueError:
            print('csv file, column 0, not a date time format:',
                  test_batch.iloc[0, 0])

    @staticmethod
    def _update_high_low(high_price, low_price, price):
        """
        Update the high and low prices using the current price.

        :param high_price: Current high price that needs to be updated
        :param low_price: Current low price that needs to be updated
        :param price: Current price
        :return: Updated high and low prices
        """
        if price > high_price:
            high_price = price

        if price <= low_price:
            low_price = price

        return high_price, low_price

    def _create_bars(self, date_time, price, high_price, low_price, list_bars):
        """
        Given the inputs, construct a bar which has the following fields: date_time, open, high, low, close, volume,
        cum_buy_volume, cum_ticks, cum_dollar_value.
        These bars are appended to list_bars, which is later used to construct the final bars DataFrame.

        :param date_time: Timestamp of the bar
        :param price: The current price
        :param high_price: Highest price in the period
        :param low_price: Lowest price in the period
        :param list_bars: List to which we append the bars
        """
        # Create bars
        open_price = self.open_price
        high_price = max(high_price, open_price)
        low_price = min(low_price, open_price)
        close_price = price
        volume = self.cum_statistics['cum_volume']
        cum_buy_volume = self.cum_statistics['cum_buy_volume']
        cum_ticks = self.cum_statistics['cum_ticks']
        cum_dollar_value = self.cum_statistics['cum_dollar_value']

        # Update bars
        list_bars.append([date_time, open_price, high_price, low_price, close_price, volume, cum_buy_volume, cum_ticks,
                          cum_dollar_value])

    def _apply_tick_rule(self, price):
        """
        Applies the tick rule as defined on page 29.

        :param price: Price at time t
        :return: The signed tick
        """
        if self.prev_price is not None:
            tick_diff = price - self.prev_price
        else:
            tick_diff = 0

        if tick_diff != 0:
            signed_tick = np.sign(tick_diff)
            self.prev_tick_rule = signed_tick
        else:
            signed_tick = self.prev_tick_rule

        return signed_tick

    def _get_imbalance(self, price, signed_tick, volume):
        """
        Get the imbalance at a point in time, denoted as Theta_t in the book, pg 29.

        :param price: Price at t
        :param signed_tick: signed tick, using the tick rule
        :param volume: Volume traded at t
        :return: Imbalance at time t
        """
        if self.metric == 'tick_imbalance' or self.metric == 'tick_run':
            imbalance = signed_tick
        elif self.metric == 'dollar_imbalance' or self.metric == 'dollar_run':
            imbalance = signed_tick * volume * price
        elif self.metric == 'volume_imbalance' or self.metric == 'volume_run':
            imbalance = signed_tick * volume
        return imbalance


class BaseImbalanceBars(BaseBars):
    """
    Base class for Imbalance Bars (EMA and Const) which implements imbalance bars calculation logic
    """

    def __init__(self, file_path, metric, batch_size, expected_imbalance_window, exp_num_ticks_init,
                 analyse_thresholds):
        """
        Constructor


        :param file_path: (String) Path to the csv file containing raw tick data in the format[date_time, price, volume]
        :param metric: (String) type of imbalance bar to create. Example: dollar_imbalance.
        :param batch_size: (Int) Number of rows to read in from the csv, per batch.
        :param expected_imbalance_window: (Int) Window used to estimate expected imbalance from previous trades
        :param exp_num_ticks_init: (Int) Initial estimate for expected number of ticks in bar.
                                         For Const Imbalance Bars expected number of ticks equals expected number of ticks init
        :param analyse_thresholds: (Bool) flag to return thresholds values (theta, exp_num_ticks, exp_imbalance) in a
                                          form of Pandas DataFrame
        """
        BaseBars.__init__(self, file_path, metric, batch_size)

        self.expected_imbalance_window = expected_imbalance_window

        self.thresholds = {'cum_theta': 0, 'expected_imbalance': np.nan, 'exp_num_ticks': exp_num_ticks_init}

        # Previous bars number of ticks and previous tick imbalances
        self.imbalance_tick_statistics = {'num_ticks_bar': [], 'imbalance_array': []}

        if analyse_thresholds is True:
            # Array of dicts: {'timestamp': value, 'cum_theta': value, 'exp_num_ticks': value, 'exp_imbalance': value}
            self.bars_thresholds = []
        else:
            self.bars_thresholds = None

    def _reset_cache(self):
        """
        Implementation of abstract method _reset_cache for imbalance bars
        """
        self.open_price = None
        self.high_price, self.low_price = -np.inf, np.inf
        self.cum_statistics = {'cum_ticks': 0, 'cum_dollar_value': 0, 'cum_volume': 0, 'cum_buy_volume': 0}
        self.thresholds['cum_theta'] = 0

    def _extract_bars(self, data):
        """
        For loop which compiles the various imbalance bars: dollar, volume, or tick.

        :param data: (DataFrame) Contains 3 columns - date_time, price, and volume.
        :return: (List) of bars built using the current batch.
        """

        # Iterate over rows
        list_bars = []
        for row in data.values:
            # Set variables
            date_time = row[0]
            price = np.float(row[1])
            volume = row[2]
            dollar_value = price * volume
            signed_tick = self._apply_tick_rule(price)

            if self.open_price is None:
                self.open_price = price

            # Update high low prices
            self.high_price, self.low_price = self._update_high_low(
                self.high_price, self.low_price, price)

            # Bar statistics calculations
            self.cum_statistics['cum_ticks'] += 1
            self.cum_statistics['cum_dollar_value'] += dollar_value
            self.cum_statistics['cum_volume'] += volume
            if signed_tick == 1:
                self.cum_statistics['cum_buy_volume'] += volume

            # Imbalance calculations
            imbalance = self._get_imbalance(price, signed_tick, volume)
            self.imbalance_tick_statistics['imbalance_array'].append(imbalance)
            self.thresholds['cum_theta'] += imbalance

            self.prev_price = price  # Update previous price for tick rule calculations

            # Get expected imbalance for the first time, when num_ticks_init passed
            if not list_bars and np.isnan(self.thresholds['expected_imbalance']):
                self.thresholds['expected_imbalance'] = self._get_expected_imbalance(
                    self.expected_imbalance_window)

            if self.bars_thresholds is not None:
                self.thresholds['timestamp'] = date_time
                self.bars_thresholds.append(dict(self.thresholds))

            self.prev_price = price  # Update previous price used for tick rule calculations

            # Check expression for possible bar generation
            if np.abs(self.thresholds['cum_theta']) > self.thresholds['exp_num_ticks'] * np.abs(
                    self.thresholds['expected_imbalance']):
                self._create_bars(date_time, price,
                                  self.high_price, self.low_price, list_bars)

                self.imbalance_tick_statistics['num_ticks_bar'].append(self.cum_statistics['cum_ticks'])
                # Expected number of ticks based on formed bars
                self.thresholds['exp_num_ticks'] = self._get_exp_num_ticks()
                # Get expected imbalance
                self.thresholds['expected_imbalance'] = self._get_expected_imbalance(
                    self.expected_imbalance_window)
                # Reset counters
                self._reset_cache()

        return list_bars

    def _get_expected_imbalance(self, window):
        """
        Calculate the expected imbalance: 2P[b_t=1]-1, using a EWMA, pg 29
        :param window: EWMA window for calculation
        :return: expected_imbalance: 2P[b_t=1]-1, approximated using a EWMA
        """
        if len(self.imbalance_tick_statistics['imbalance_array']) < self.thresholds['exp_num_ticks']:
            # Waiting for array to fill for ewma
            ewma_window = np.nan
        else:
            # ewma window can be either the window specified in a function call
            # or it is len of imbalance_array if window > len(imbalance_array)
            ewma_window = int(min(len(self.imbalance_tick_statistics['imbalance_array']), window))

        if np.isnan(ewma_window):
            # return nan, wait until len(self.imbalance_array) >= self.exp_num_ticks_init
            expected_imbalance = np.nan
        else:
            expected_imbalance = ewma(
                np.array(self.imbalance_tick_statistics['imbalance_array'][-ewma_window:], dtype=float),
                window=ewma_window)[-1]

        return expected_imbalance

    @abstractmethod
    def _get_exp_num_ticks(self):
        """
        Abstract method which updates expected number of ticks when new run bar is formed
        """


# pylint: disable=too-many-instance-attributes
class BaseRunBars(BaseBars):
    """
    Base class for Run Bars (EMA and Const) which implements run bars calculation logic
    """

    def __init__(self, file_path, metric, batch_size, num_prev_bars, expected_imbalance_window, exp_num_ticks_init,
                 analyse_thresholds):
        """
        Constructor


        :param file_path: (String) Path to the csv file containing raw tick data in the format[date_time, price, volume]
        :param metric: (String) type of imbalance bar to create. Example: dollar_imbalance.
        :param batch_size: (Int) Number of rows to read in from the csv, per batch.
        :param expected_imbalance_window: (Int) Window used to estimate expected imbalance from previous trades
        :param exp_num_ticks_init: (Int) Initial estimate for expected number of ticks in bar.
                                         For Const Imbalance Bars expected number of ticks equals expected number of ticks init
        :param analyse_thresholds: (Bool) flag to return thresholds values (thetas, exp_num_ticks, exp_imbalances) in Pandas DataFrame
        """
        BaseBars.__init__(self, file_path, metric, batch_size)

        self.num_prev_bars = num_prev_bars
        self.expected_imbalance_window = expected_imbalance_window

        self.thresholds = {'cum_theta_buy': 0, 'cum_theta_sell': 0, 'exp_imbalance_buy': np.nan,
                           'exp_imbalance_sell': np.nan, 'exp_num_ticks': exp_num_ticks_init,
                           'exp_buy_ticks_proportion': np.nan, 'buy_ticks_num': 0}

        # Previous bars number of ticks and previous tick imbalances
        self.imbalance_tick_statistics = {'num_ticks_bar': [], 'imbalance_array_buy': [], 'imbalance_array_sell': [],
                                          'buy_ticks_proportion': []}

        if analyse_thresholds:
            # Array of dicts: {'timestamp': value, 'cum_theta': value, 'exp_num_ticks': value, 'exp_imbalance': value}
            self.bars_thresholds = []
        else:
            self.bars_thresholds = None

        self.imbalances_are_counted_flag = False

    def _reset_cache(self):
        """
        Implementation of abstract method _reset_cache for imbalance bars
        """
        self.open_price = None
        self.high_price, self.low_price = -np.inf, np.inf
        self.cum_statistics = {'cum_ticks': 0, 'cum_dollar_value': 0, 'cum_volume': 0, 'cum_buy_volume': 0}
        self.thresholds['cum_theta_buy'], self.thresholds['cum_theta_sell'], self.thresholds['buy_ticks_num'] = 0, 0, 0

    def _extract_bars(self, data):
        """
        For loop which compiles the various run bars: dollar, volume, or tick.

        :param data: (DataFrame) Contains 3 columns - date_time, price, and volume.
        :return: (List) of bars built using the current batch.
        """

        # Iterate over rows
        list_bars = []
        for row in data.values:
            # Set variables
            date_time = row[0]
            price = np.float(row[1])
            volume = row[2]
            dollar_value = price * volume
            signed_tick = self._apply_tick_rule(price)

            if self.open_price is None:
                self.open_price = price

            # Update high low prices
            self.high_price, self.low_price = self._update_high_low(
                self.high_price, self.low_price, price)

            # Bar statistics calculations
            self.cum_statistics['cum_ticks'] += 1
            self.cum_statistics['cum_dollar_value'] += dollar_value
            self.cum_statistics['cum_volume'] += volume
            if signed_tick == 1:
                self.cum_statistics['cum_buy_volume'] += volume

            # Imbalance calculations
            imbalance = self._get_imbalance(price, signed_tick, volume)

            if imbalance > 0:
                self.imbalance_tick_statistics['imbalance_array_buy'].append(imbalance)
                self.thresholds['cum_theta_buy'] += imbalance
                self.thresholds['buy_ticks_num'] += 1
            elif imbalance < 0:
                self.imbalance_tick_statistics['imbalance_array_sell'].append(abs(imbalance))
                self.thresholds['cum_theta_sell'] += abs(imbalance)

            self.imbalances_are_counted_flag = np.isnan([self.thresholds['exp_imbalance_buy'], self.thresholds[
                'exp_imbalance_sell']]).any()  # Flag indicating that both buy and sell imbalances are counted

            self.prev_price = price  # Update previous price for tick rule calculations

            # Get expected imbalance for the first time, when num_ticks_init passed
            if not list_bars and self.imbalances_are_counted_flag:

                self.thresholds['exp_imbalance_buy'] = self._get_expected_imbalance(
                    self.imbalance_tick_statistics['imbalance_array_buy'], self.expected_imbalance_window, warm_up=True)
                self.thresholds['exp_imbalance_sell'] = self._get_expected_imbalance(
                    self.imbalance_tick_statistics['imbalance_array_sell'], self.expected_imbalance_window,
                    warm_up=True)

                if bool(np.isnan([self.thresholds['exp_imbalance_buy'],
                                  self.thresholds['exp_imbalance_sell']]).any()) is False:
                    self.thresholds['exp_buy_ticks_proportion'] = self.thresholds['buy_ticks_num'] / \
                                                                  self.cum_statistics[
                                                                      'cum_ticks']

            if self.bars_thresholds is not None:
                self.thresholds['timestamp'] = date_time
                self.bars_thresholds.append(dict(self.thresholds))

            self.prev_price = price  # Update previous price used for tick rule calculations

            # Check expression for possible bar generation
            max_proportion = max(
                self.thresholds['exp_imbalance_buy'] * self.thresholds['exp_buy_ticks_proportion'],
                self.thresholds['exp_imbalance_sell'] * (1 - self.thresholds['exp_buy_ticks_proportion']))

            # Check expression for possible bar generation
            max_theta = max(self.thresholds['cum_theta_buy'], self.thresholds['cum_theta_sell'])
            if max_theta > self.thresholds['exp_num_ticks'] * max_proportion and not np.isnan(max_proportion):
                self._create_bars(date_time, price, self.high_price, self.low_price, list_bars)

                self.imbalance_tick_statistics['num_ticks_bar'].append(self.cum_statistics['cum_ticks'])
                self.imbalance_tick_statistics['buy_ticks_proportion'].append(
                    self.thresholds['buy_ticks_num'] / self.cum_statistics['cum_ticks'])

                # Expected number of ticks based on formed bars
                self.thresholds['exp_num_ticks'] = self._get_exp_num_ticks()

                # Expected buy ticks proportion based on formed bars
                exp_buy_ticks_proportion = ewma(
                    np.array(self.imbalance_tick_statistics['buy_ticks_proportion'][-self.num_prev_bars:], dtype=float),
                    self.num_prev_bars)[-1]
                self.thresholds['exp_buy_ticks_proportion'] = exp_buy_ticks_proportion

                # Get expected imbalance
                self.thresholds['exp_imbalance_buy'] = self._get_expected_imbalance(
                    self.imbalance_tick_statistics['imbalance_array_buy'], self.expected_imbalance_window)
                self.thresholds['exp_imbalance_sell'] = self._get_expected_imbalance(
                    self.imbalance_tick_statistics['imbalance_array_sell'], self.expected_imbalance_window)

                # Reset counters
                self._reset_cache()

        return list_bars

    def _get_expected_imbalance(self, array, window, warm_up=False):
        """
        Calculate the expected imbalance: 2P[b_t=1]-1, using a EWMA, pg 29
        :param window: EWMA window for calculation
        :parawm warm_up: boolean flag of whether warm up period passed
        :return: expected_imbalance: 2P[b_t=1]-1, approximated using a EWMA
        """
        if len(array) < self.thresholds['exp_num_ticks'] and warm_up is True:
            # Waiting for array to fill for ewma
            ewma_window = np.nan
        else:
            # ewma window can be either the window specified in a function call
            # or it is len of imbalance_array if window > len(imbalance_array)
            ewma_window = int(min(len(array), window))

        if np.isnan(ewma_window):
            # return nan, wait until len(self.imbalance_array) >= self.exp_num_ticks_init
            expected_imbalance = np.nan
        else:
            expected_imbalance = ewma(
                np.array(array[-ewma_window:], dtype=float),
                window=ewma_window)[-1]

        return expected_imbalance

    @abstractmethod
    def _get_exp_num_ticks(self):
        """
        Abstract method which updates expected number of ticks when new imbalance bar is formed
        """
