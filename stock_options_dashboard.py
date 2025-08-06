#!/usr/bin/env python3
"""
Stock Options Dashboard for Google Colab
A self-contained Flask web application that displays live stock options data
with interactive filtering and Greeks analysis.
"""

# Install required packages
import subprocess
import sys

def install_packages():
    packages = [
        'flask',
        'yfinance',
        'pandas',
        'numpy',
        'requests',
        'flask-cors',
        'threading'
    ]
    
    for package in packages:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {package}")

print("Installing required packages...")
install_packages()
print("Package installation complete!\n")

# Import libraries
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import threading
import time
import json
from scipy.stats import norm
import warnings
warnings.filterwarnings('ignore')

# Global variables
app = Flask(__name__)
CORS(app)
options_data = {}
tickers_list = []

def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    """
    Calculate Black-Scholes Greeks
    S: Current stock price
    K: Strike price
    T: Time to expiration (in years)
    r: Risk-free rate
    sigma: Implied volatility
    """
    if T <= 0 or sigma <= 0:
        return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
    
    try:
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == 'call':
            delta = norm.cdf(d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                    - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        else:  # put
            delta = -norm.cdf(-d1)
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                    + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
        
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        
        return {
            'delta': round(delta, 4),
            'gamma': round(gamma, 4),
            'theta': round(theta, 4),
            'vega': round(vega, 4)
        }
    except:
        return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}

def get_target_expiration_dates(current_date, target_days=[90, 120, 150]):
    """Get target expiration dates approximately 90, 120, and 150 days out"""
    target_dates = []
    for days in target_days:
        target_date = current_date + timedelta(days=days)
        target_dates.append(target_date)
    return target_dates

def find_closest_expiration(available_dates, target_date):
    """Find the closest available expiration date to the target"""
    if not available_dates:
        return None
    
    available_dates = [datetime.strptime(date, '%Y-%m-%d').date() if isinstance(date, str) else date for date in available_dates]
    target_date = target_date.date() if isinstance(target_date, datetime) else target_date
    
    closest_date = min(available_dates, key=lambda x: abs((x - target_date).days))
    return closest_date.strftime('%Y-%m-%d')

def fetch_options_data(ticker_symbol):
    """Fetch options data for a given ticker"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        stock_info = ticker.info
        current_price = stock_info.get('currentPrice', stock_info.get('regularMarketPrice', 0))
        
        if current_price == 0:
            # Fallback to history
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
        
        expiration_dates = ticker.options
        if not expiration_dates:
            return None
        
        current_date = datetime.now()
        target_dates = get_target_expiration_dates(current_date)
        
        selected_expirations = []
        for target_date in target_dates:
            closest_exp = find_closest_expiration(expiration_dates, target_date)
            if closest_exp and closest_exp not in selected_expirations:
                selected_expirations.append(closest_exp)
        
        options_data_by_exp = {}
        
        for exp_date in selected_expirations:
            try:
                option_chain = ticker.option_chain(exp_date)
                calls = option_chain.calls
                puts = option_chain.puts
                
                # Calculate days to expiration
                exp_datetime = datetime.strptime(exp_date, '%Y-%m-%d')
                days_to_exp = (exp_datetime - current_date).days
                time_to_exp = days_to_exp / 365.0
                
                # Process calls
                calls_processed = []
                for _, call in calls.iterrows():
                    greeks = black_scholes_greeks(
                        current_price, call['strike'], time_to_exp, 0.02, 
                        call.get('impliedVolatility', 0.2), 'call'
                    )
                    
                    calls_processed.append({
                        'strike': call['strike'],
                        'lastPrice': call.get('lastPrice', 0),
                        'bid': call.get('bid', 0),
                        'ask': call.get('ask', 0),
                        'volume': call.get('volume', 0),
                        'openInterest': call.get('openInterest', 0),
                        'impliedVolatility': call.get('impliedVolatility', 0),
                        'delta': greeks['delta'],
                        'gamma': greeks['gamma'],
                        'theta': greeks['theta'],
                        'vega': greeks['vega'],
                        'daysToExpiration': days_to_exp
                    })
                
                # Process puts
                puts_processed = []
                for _, put in puts.iterrows():
                    greeks = black_scholes_greeks(
                        current_price, put['strike'], time_to_exp, 0.02, 
                        put.get('impliedVolatility', 0.2), 'put'
                    )
                    
                    puts_processed.append({
                        'strike': put['strike'],
                        'lastPrice': put.get('lastPrice', 0),
                        'bid': put.get('bid', 0),
                        'ask': put.get('ask', 0),
                        'volume': put.get('volume', 0),
                        'openInterest': put.get('openInterest', 0),
                        'impliedVolatility': put.get('impliedVolatility', 0),
                        'delta': greeks['delta'],
                        'gamma': greeks['gamma'],
                        'theta': greeks['theta'],
                        'vega': greeks['vega'],
                        'daysToExpiration': days_to_exp
                    })
                
                options_data_by_exp[exp_date] = {
                    'calls': calls_processed,
                    'puts': puts_processed,
                    'daysToExpiration': days_to_exp
                }
                
            except Exception as e:
                print(f"Error processing {exp_date} for {ticker_symbol}: {e}")
                continue
        
        return {
            'ticker': ticker_symbol,
            'currentPrice': current_price,
            'expirations': options_data_by_exp
        }
        
    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return None

def update_options_data():
    """Update options data for all tickers"""
    global options_data
    for ticker in tickers_list:
        print(f"Fetching data for {ticker}...")
        data = fetch_options_data(ticker)
        if data:
            options_data[ticker] = data
            print(f"✓ Updated data for {ticker}")
        else:
            print(f"✗ Failed to fetch data for {ticker}")

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Options Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .controls {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }
        
        .filter-section {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .filter-group {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .filter-group h3 {
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 1.1em;
        }
        
        .filter-input {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .filter-input label {
            font-weight: 600;
            color: #555;
            font-size: 0.9em;
        }
        
        .filter-input input, .filter-input select {
            padding: 10px;
            border: 2px solid #e9ecef;
            border-radius: 5px;
            font-size: 1em;
            transition: border-color 0.3s;
        }
        
        .filter-input input:focus, .filter-input select:focus {
            outline: none;
            border-color: #3498db;
        }
        
        .buttons {
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 25px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
        }
        
        .btn-secondary {
            background: linear-gradient(135deg, #95a5a6, #7f8c8d);
            color: white;
        }
        
        .btn-success {
            background: linear-gradient(135deg, #27ae60, #229954);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 1.2em;
            color: #666;
        }
        
        .ticker-section {
            margin: 30px;
            background: white;
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .ticker-header {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .ticker-header h2 {
            font-size: 1.8em;
        }
        
        .current-price {
            font-size: 1.5em;
            font-weight: bold;
        }
        
        .expiration-section {
            margin: 20px 30px;
        }
        
        .expiration-header {
            background: #34495e;
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .expiration-header h3 {
            font-size: 1.3em;
        }
        
        .options-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        .options-type {
            background: #f8f9fa;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .options-type h4 {
            background: #2c3e50;
            color: white;
            padding: 15px;
            margin: 0;
            font-size: 1.2em;
            text-align: center;
        }
        
        .calls-header {
            background: #27ae60 !important;
        }
        
        .puts-header {
            background: #e74c3c !important;
        }
        
        .options-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .options-table th {
            background: #ecf0f1;
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            color: #2c3e50;
            font-size: 0.9em;
            border-bottom: 2px solid #bdc3c7;
        }
        
        .options-table td {
            padding: 10px 8px;
            text-align: center;
            border-bottom: 1px solid #ecf0f1;
            font-size: 0.85em;
        }
        
        .options-table tr:hover {
            background: #f1f2f6;
        }
        
        .atm-row {
            background: #fff3cd !important;
            font-weight: bold;
        }
        
        .notes {
            margin: 30px;
            padding: 25px;
            background: #f8f9fa;
            border-radius: 15px;
            border-left: 5px solid #3498db;
        }
        
        .notes h3 {
            color: #2c3e50;
            margin-bottom: 20px;
            font-size: 1.4em;
        }
        
        .greeks-explanation {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .greek-item {
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .greek-item h4 {
            color: #e74c3c;
            margin-bottom: 8px;
        }
        
        .conservative-section {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .conservative-section h4 {
            color: #27ae60;
            margin-bottom: 15px;
        }
        
        .conservative-list {
            list-style: none;
            padding: 0;
        }
        
        .conservative-list li {
            padding: 8px 0;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .conservative-list li:last-child {
            border-bottom: none;
        }
        
        @media (max-width: 768px) {
            .options-container {
                grid-template-columns: 1fr;
            }
            
            .filter-section {
                grid-template-columns: 1fr;
            }
            
            .buttons {
                flex-direction: column;
            }
            
            .ticker-header {
                flex-direction: column;
                gap: 10px;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Stock Options Dashboard</h1>
            <p>Interactive Options Analysis with Greeks & Filtering</p>
        </div>
        
        <div class="controls">
            <div class="filter-section">
                <div class="filter-group">
                    <h3>Greeks Filters</h3>
                    <div class="filter-input">
                        <label>Delta Range:</label>
                        <input type="number" id="deltaMin" step="0.01" placeholder="Min Delta">
                        <input type="number" id="deltaMax" step="0.01" placeholder="Max Delta">
                    </div>
                </div>
                
                <div class="filter-group">
                    <h3>Volume & Interest</h3>
                    <div class="filter-input">
                        <label>Min Volume:</label>
                        <input type="number" id="minVolume" placeholder="Min Volume">
                        <label>Min Open Interest:</label>
                        <input type="number" id="minOpenInterest" placeholder="Min OI">
                    </div>
                </div>
                
                <div class="filter-group">
                    <h3>Days to Expiration</h3>
                    <div class="filter-input">
                        <label>Min Days:</label>
                        <input type="number" id="minDays" placeholder="Min Days">
                        <label>Max Days:</label>
                        <input type="number" id="maxDays" placeholder="Max Days">
                    </div>
                </div>
                
                <div class="filter-group">
                    <h3>Advanced Greeks</h3>
                    <div class="filter-input">
                        <label>Max Theta (absolute):</label>
                        <input type="number" id="maxTheta" step="0.01" placeholder="Max |Theta|">
                        <label>Min Vega:</label>
                        <input type="number" id="minVega" step="0.01" placeholder="Min Vega">
                    </div>
                </div>
            </div>
            
            <div class="buttons">
                <button class="btn btn-success" onclick="applyConservativeFilters()">Conservative Defaults</button>
                <button class="btn btn-primary" onclick="applyFilters()">Apply Filters</button>
                <button class="btn btn-secondary" onclick="clearFilters()">Clear Filters</button>
                <button class="btn btn-primary" onclick="toggleATM()">Toggle ATM Only</button>
                <button class="btn btn-secondary" onclick="refreshData()">Refresh Data</button>
            </div>
        </div>
        
        <div id="content">
            <div class="loading">
                <p>📊 Loading options data...</p>
                <p>This may take a few moments for multiple tickers.</p>
            </div>
        </div>
        
        <div class="notes">
            <h3>📚 Greeks Explained</h3>
            <div class="greeks-explanation">
                <div class="greek-item">
                    <h4>Delta (Δ)</h4>
                    <p>Measures price sensitivity to underlying stock movement. Call deltas range 0-1, put deltas range -1-0. Higher absolute delta = more price movement per $1 stock change.</p>
                </div>
                <div class="greek-item">
                    <h4>Gamma (Γ)</h4>
                    <p>Rate of change of delta. Higher gamma means delta changes rapidly as stock price moves. ATM options have highest gamma.</p>
                </div>
                <div class="greek-item">
                    <h4>Theta (Θ)</h4>
                    <p>Time decay. Shows daily option value loss due to time passage. Always negative for long positions. Higher absolute theta = faster decay.</p>
                </div>
                <div class="greek-item">
                    <h4>Vega (ν)</h4>
                    <p>Volatility sensitivity. Shows option price change per 1% volatility change. Higher vega = more sensitive to volatility changes.</p>
                </div>
            </div>
            
            <div class="conservative-section">
                <h4>🛡️ Conservative Trading Guidelines</h4>
                <ul class="conservative-list">
                    <li><strong>Delta:</strong> 0.15-0.85 for calls, -0.85 to -0.15 for puts (avoid extreme ITM/OTM)</li>
                    <li><strong>Volume:</strong> Minimum 50 contracts for liquidity</li>
                    <li><strong>Open Interest:</strong> Minimum 100 contracts for market depth</li>
                    <li><strong>Days to Expiration:</strong> 30-120 days (avoid weekly options)</li>
                    <li><strong>Theta:</strong> Maximum absolute value of 0.05 to limit time decay</li>
                    <li><strong>Implied Volatility:</strong> Compare to historical volatility for fair pricing</li>
                    <li><strong>ATM Filter:</strong> Focus on strikes within ±3 of current price for balanced risk/reward</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        let allData = {};
        let filteredData = {};
        let atmOnly = false;
        
        async function loadData() {
            try {
                const response = await fetch('/api/options');
                allData = await response.json();
                filteredData = JSON.parse(JSON.stringify(allData));
                renderData();
            } catch (error) {
                console.error('Error loading data:', error);
                document.getElementById('content').innerHTML = '<div class="loading"><p>❌ Error loading data. Please refresh the page.</p></div>';
            }
        }
        
        function applyConservativeFilters() {
            document.getElementById('deltaMin').value = '0.15';
            document.getElementById('deltaMax').value = '0.85';
            document.getElementById('minVolume').value = '50';
            document.getElementById('minOpenInterest').value = '100';
            document.getElementById('minDays').value = '30';
            document.getElementById('maxDays').value = '120';
            document.getElementById('maxTheta').value = '0.05';
            document.getElementById('minVega').value = '0.01';
            applyFilters();
        }
        
        function applyFilters() {
            const filters = {
                deltaMin: parseFloat(document.getElementById('deltaMin').value) || -1,
                deltaMax: parseFloat(document.getElementById('deltaMax').value) || 1,
                minVolume: parseInt(document.getElementById('minVolume').value) || 0,
                minOpenInterest: parseInt(document.getElementById('minOpenInterest').value) || 0,
                minDays: parseInt(document.getElementById('minDays').value) || 0,
                maxDays: parseInt(document.getElementById('maxDays').value) || 365,
                maxTheta: parseFloat(document.getElementById('maxTheta').value) || 1,
                minVega: parseFloat(document.getElementById('minVega').value) || 0
            };
            
            filteredData = {};
            
            for (const ticker in allData) {
                filteredData[ticker] = {
                    ...allData[ticker],
                    expirations: {}
                };
                
                for (const expDate in allData[ticker].expirations) {
                    const expData = allData[ticker].expirations[expDate];
                    
                    // Filter calls
                    const filteredCalls = expData.calls.filter(option => 
                        filterOption(option, filters, 'call', allData[ticker].currentPrice)
                    );
                    
                    // Filter puts
                    const filteredPuts = expData.puts.filter(option => 
                        filterOption(option, filters, 'put', allData[ticker].currentPrice)
                    );
                    
                    if (filteredCalls.length > 0 || filteredPuts.length > 0) {
                        filteredData[ticker].expirations[expDate] = {
                            ...expData,
                            calls: filteredCalls,
                            puts: filteredPuts
                        };
                    }
                }
            }
            
            renderData();
        }
        
        function filterOption(option, filters, type, currentPrice) {
            // Days to expiration filter
            if (option.daysToExpiration < filters.minDays || option.daysToExpiration > filters.maxDays) {
                return false;
            }
            
            // Volume and Open Interest filters
            if (option.volume < filters.minVolume || option.openInterest < filters.minOpenInterest) {
                return false;
            }
            
            // Delta filter (considering call/put differences)
            if (type === 'call') {
                if (option.delta < filters.deltaMin || option.delta > filters.deltaMax) {
                    return false;
                }
            } else { // put
                if (option.delta > -filters.deltaMin || option.delta < -filters.deltaMax) {
                    return false;
                }
            }
            
            // Theta filter (absolute value)
            if (Math.abs(option.theta) > filters.maxTheta) {
                return false;
            }
            
            // Vega filter
            if (option.vega < filters.minVega) {
                return false;
            }
            
            // ATM filter
            if (atmOnly) {
                const priceDiff = Math.abs(option.strike - currentPrice);
                const atmThreshold = currentPrice * 0.05; // 5% threshold
                if (priceDiff > atmThreshold) {
                    return false;
                }
            }
            
            return true;
        }
        
        function clearFilters() {
            document.getElementById('deltaMin').value = '';
            document.getElementById('deltaMax').value = '';
            document.getElementById('minVolume').value = '';
            document.getElementById('minOpenInterest').value = '';
            document.getElementById('minDays').value = '';
            document.getElementById('maxDays').value = '';
            document.getElementById('maxTheta').value = '';
            document.getElementById('minVega').value = '';
            
            filteredData = JSON.parse(JSON.stringify(allData));
            renderData();
        }
        
        function toggleATM() {
            atmOnly = !atmOnly;
            applyFilters();
        }
        
        function isATM(strike, currentPrice) {
            return Math.abs(strike - currentPrice) <= currentPrice * 0.03; // 3% threshold
        }
        
        function renderData() {
            let html = '';
            
            if (Object.keys(filteredData).length === 0) {
                html = '<div class="loading"><p>No data available or all options filtered out.</p></div>';
            } else {
                for (const ticker in filteredData) {
                    const tickerData = filteredData[ticker];
                    html += `
                        <div class="ticker-section">
                            <div class="ticker-header">
                                <h2>${ticker}</h2>
                                <div class="current-price">$${tickerData.currentPrice.toFixed(2)}</div>
                            </div>
                    `;
                    
                    for (const expDate in tickerData.expirations) {
                        const expData = tickerData.expirations[expDate];
                        html += `
                            <div class="expiration-section">
                                <div class="expiration-header">
                                    <h3>Expiration: ${expDate} (${expData.daysToExpiration} days)</h3>
                                </div>
                                <div class="options-container">
                        `;
                        
                        // Calls
                        html += `
                            <div class="options-type">
                                <h4 class="calls-header">CALLS (${expData.calls.length})</h4>
                                <table class="options-table">
                                    <thead>
                                        <tr>
                                            <th>Strike</th>
                                            <th>Last</th>
                                            <th>Bid</th>
                                            <th>Ask</th>
                                            <th>Vol</th>
                                            <th>OI</th>
                                            <th>IV</th>
                                            <th>Δ</th>
                                            <th>Γ</th>
                                            <th>Θ</th>
                                            <th>ν</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        `;
                        
                        expData.calls.forEach(call => {
                            const isAtmOption = isATM(call.strike, tickerData.currentPrice);
                            html += `
                                <tr ${isAtmOption ? 'class="atm-row"' : ''}>
                                    <td>$${call.strike.toFixed(2)}</td>
                                    <td>$${call.lastPrice.toFixed(2)}</td>
                                    <td>$${call.bid.toFixed(2)}</td>
                                    <td>$${call.ask.toFixed(2)}</td>
                                    <td>${call.volume}</td>
                                    <td>${call.openInterest}</td>
                                    <td>${(call.impliedVolatility * 100).toFixed(1)}%</td>
                                    <td>${call.delta.toFixed(3)}</td>
                                    <td>${call.gamma.toFixed(4)}</td>
                                    <td>${call.theta.toFixed(3)}</td>
                                    <td>${call.vega.toFixed(3)}</td>
                                </tr>
                            `;
                        });
                        
                        html += `
                                    </tbody>
                                </table>
                            </div>
                        `;
                        
                        // Puts
                        html += `
                            <div class="options-type">
                                <h4 class="puts-header">PUTS (${expData.puts.length})</h4>
                                <table class="options-table">
                                    <thead>
                                        <tr>
                                            <th>Strike</th>
                                            <th>Last</th>
                                            <th>Bid</th>
                                            <th>Ask</th>
                                            <th>Vol</th>
                                            <th>OI</th>
                                            <th>IV</th>
                                            <th>Δ</th>
                                            <th>Γ</th>
                                            <th>Θ</th>
                                            <th>ν</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        `;
                        
                        expData.puts.forEach(put => {
                            const isAtmOption = isATM(put.strike, tickerData.currentPrice);
                            html += `
                                <tr ${isAtmOption ? 'class="atm-row"' : ''}>
                                    <td>$${put.strike.toFixed(2)}</td>
                                    <td>$${put.lastPrice.toFixed(2)}</td>
                                    <td>$${put.bid.toFixed(2)}</td>
                                    <td>$${put.ask.toFixed(2)}</td>
                                    <td>${put.volume}</td>
                                    <td>${put.openInterest}</td>
                                    <td>${(put.impliedVolatility * 100).toFixed(1)}%</td>
                                    <td>${put.delta.toFixed(3)}</td>
                                    <td>${put.gamma.toFixed(4)}</td>
                                    <td>${put.theta.toFixed(3)}</td>
                                    <td>${put.vega.toFixed(3)}</td>
                                </tr>
                            `;
                        });
                        
                        html += `
                                    </tbody>
                                </table>
                            </div>
                        `;
                        
                        html += `
                                </div>
                            </div>
                        `;
                    }
                    
                    html += '</div>';
                }
            }
            
            document.getElementById('content').innerHTML = html;
        }
        
        async function refreshData() {
            document.getElementById('content').innerHTML = '<div class="loading"><p>🔄 Refreshing data...</p></div>';
            await fetch('/api/refresh', { method: 'POST' });
            setTimeout(loadData, 2000); // Wait a bit for data to refresh
        }
        
        // Load data when page loads
        window.onload = function() {
            setTimeout(loadData, 1000);
        };
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/options')
def get_options():
    return jsonify(options_data)

@app.route('/api/refresh', methods=['POST'])
def refresh_options():
    threading.Thread(target=update_options_data, daemon=True).start()
    return jsonify({"status": "refreshing"})

def run_flask_app():
    """Run Flask app in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    """Main function to run the dashboard"""
    global tickers_list
    
    print("🚀 Stock Options Dashboard")
    print("=" * 50)
    
    # Get ticker symbols from user
    tickers_input = input("Enter comma-separated ticker symbols (e.g., AAPL,MSFT,TSLA): ").strip()
    if not tickers_input:
        print("No tickers provided. Using default: AAPL,MSFT,TSLA")
        tickers_input = "AAPL,MSFT,TSLA"
    
    tickers_list = [ticker.strip().upper() for ticker in tickers_input.split(',')]
    print(f"Fetching data for: {', '.join(tickers_list)}")
    
    # Initial data fetch
    print("\n📊 Fetching initial options data...")
    update_options_data()
    
    # Start Flask app in background thread
    print("\n🌐 Starting web server...")
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # Wait a moment for server to start
    time.sleep(2)
    
    print("\n✅ Dashboard is ready!")
    print("🔗 Access your dashboard at: http://localhost:5000")
    print("\n📋 Features available:")
    print("• Interactive filtering by Greeks, volume, and days to expiration")
    print("• Conservative defaults button for safe trading parameters")
    print("• At-the-money (ATM) filter showing ±3 strike prices from current price")
    print("• Real-time data refresh capability")
    print("• Comprehensive Greeks calculations and explanations")
    print("• Mobile-responsive design")
    
    print("\n⚠️  Note: Keep this cell running to maintain the web server!")
    print("Press Ctrl+C to stop the server when done.")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down dashboard...")

if __name__ == "__main__":
    main()