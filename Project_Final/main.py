"""
Created on Mon May 21 09:39:10 2018

@author: gowtham
"""

"""Compute the Parameters for the Model """

import os
import pandas as pd
import matplotlib.pyplot as plt

"""   Compute the Path of the Data File  """

def symbol_to_path(symbol, base_dir="stock_data"):
    """Return CSV file path given ticker symbol."""
    return os.path.join(base_dir, "{}.csv".format(str(symbol)))

def symbol_to_path_News(symbol, base_dir="news"):
    """Return CSV file path given ticker symbol."""
    return os.path.join(base_dir, "{}.csv".format(str(symbol)))

"""Compute data into dataframes  """

def get_data(symbols, dates):
    """Read stock data (adjusted close) for given symbols from CSV files."""
    df = pd.DataFrame(index=dates)
    for symbol in symbols:
        df_temp = pd.read_csv(symbol_to_path(symbol), index_col='Date',
                parse_dates=True, usecols=['Date', 'Open'], na_values=['nan'])
        df_temp = df_temp.rename(columns={'Open': symbol})
        df = df.join(df_temp)
        if symbol == 'NSEI':  # drop dates NSEI did not trade
            df = df.dropna(subset=["NSEI"])
    df.fillna(method='ffill',inplace=True)
    df.fillna(method='bfill',inplace=True)
    df[1:]=((df[1:]/df[:-1].values)-1)*100
    df.iloc[0, :]=0
    return df

def get_rolling_std(dates,datafra, window):
    """Return rolling standard deviation of given values, using specified window size."""
    df_std = pd.DataFrame(index=dates) 
    df_std = df_std.join(datafra['Open'].rolling(window=window).std())
    df_std = df_std.rename(columns={'Open': 'std'}) 
    df_std = df_std.dropna(subset=["std"])
    return df_std

def get_stock_data(symbol, dates):
    """Read stock data (adjusted close) for given symbols from CSV files."""
    df = pd.DataFrame(index=dates)
    df_temp = pd.read_csv(symbol_to_path(symbol), index_col='Date',
            parse_dates=True, usecols=['Date', 'Open'], na_values=['nan'])
    df_news = pd.read_csv(symbol_to_path_News(symbol),index_col='date',
                          parse_dates=True,usecols=['date','positive','negative','neutral','compound'], na_values=['nan'])
    df_news = df_news.rename(columns={'date': 'Date'})
    #print(df_news)
    df_news['positive'].fillna(0,inplace=True)
    df_news['compound'].fillna(0,inplace=True)
    df_news['negative'].fillna(0,inplace=True)
    df_news['neutral'].fillna(1,inplace=True)
    daily_returns = df_temp.copy()
    daily_returns[1:] = ((daily_returns[1:]/daily_returns[:-1].values)-1)*100
    daily_returns.iloc[0, :] = 0
    daily_returns = daily_returns.rename(columns={'Open': 'Daily'})
    df_temp['Daily']=daily_returns['Daily']
    df_temp = df_temp.join(df_news)
    df = df.join(df_temp)
    df.fillna(method='ffill',inplace=True)
    df.fillna(method='bfill',inplace=True)
    return df


def test_run():
    # Read data
    dates = pd.date_range('2018-01-02', '2018-05-17')  # all dates in csv
    symbol = 'SBIN.NS'
    symbols = ['NSEI','BSESN','N225','IXIC']
    df = get_stock_data(symbol, dates)
    df_index = get_data(symbols,dates)
    df=df.join(df_index)
    df = df.dropna(subset=["NSEI"])
    df= df.join(get_rolling_std(dates,df,20))
    df.fillna(method='bfill',inplace=True)
    df.drop_duplicates(subset=['Open','std'], keep='first',inplace=True)
    print(df)


if __name__ == "__main__":
    test_run()