#!/usr/bin/env python3
"""
Stock Options Dashboard for Google Colab with ngrok Integration
A self-contained Flask web application for analyzing stock options data with Greeks

🚀 GOOGLE COLAB SETUP INSTRUCTIONS:
1. Run this entire script in a single Colab cell
2. For public access via ngrok:
   - Sign up for free at: https://ngrok.com
   - Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken  
   - Run: !ngrok authtoken YOUR_TOKEN_HERE
   - Or uncomment and modify the ngrok.set_auth_token() line below
3. Access your dashboard via the provided public URL
4. Share the public URL with anyone to access your dashboard!

📋 FEATURES:
• Interactive options data analysis for multiple tickers
• Complete Greeks calculations (Delta, Gamma, Theta, Vega)
• Advanced filtering system with conservative presets
• At-the-money (ATM) filtering
• Days to expiration filtering
• Educational content about options trading
• Mobile-responsive design
• Public access via ngrok tunnel
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
        'scipy',
        'requests',
        'flask-cors',
        'pyngrok'
    ]
    
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

install_packages()

import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import norm
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
from pyngrok import ngrok
import json
import warnings
warnings.filterwarnings('ignore')

class OptionsAnalyzer:
    def __init__(self):
        self.data_cache = {}
        self.cache_timestamp = {}
        self.cache_duration = 300  # 5 minutes
    
    def get_risk_free_rate(self):
        """Get current risk-free rate (10-year Treasury)"""
        try:
            treasury = yf.Ticker("^TNX")
            hist = treasury.history(period="5d")
            if not hist.empty:
                return hist['Close'].iloc[-1] / 100
        except:
            pass
        return 0.045  # Default 4.5%
    
    def calculate_greeks(self, S, K, T, r, sigma, option_type='call'):
        """Calculate option Greeks using Black-Scholes model"""
        if T <= 0 or sigma <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
        
        try:
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            if option_type == 'call':
                delta = norm.cdf(d1)
                theta = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
                        - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
            else:  # put
                delta = norm.cdf(d1) - 1
                theta = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
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
    
    def get_options_data(self, ticker, target_days=[90, 120, 150]):
        """Fetch options data for specified ticker and target days"""
        cache_key = f"{ticker}_{'-'.join(map(str, target_days))}"
        
        # Check cache
        if (cache_key in self.data_cache and 
            cache_key in self.cache_timestamp and
            time.time() - self.cache_timestamp[cache_key] < self.cache_duration):
            return self.data_cache[cache_key]
        
        try:
            stock = yf.Ticker(ticker)
            stock_info = stock.info
            current_price = stock_info.get('currentPrice', stock_info.get('regularMarketPrice', 0))
            
            if current_price == 0:
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            expirations = stock.options
            if not expirations:
                return None
            
            current_date = datetime.now()
            target_expirations = []
            
            # Find closest expiration dates to target days
            for target_days_val in target_days:
                target_date = current_date + timedelta(days=target_days_val)
                closest_exp = None
                min_diff = float('inf')
                
                for exp_str in expirations:
                    exp_date = datetime.strptime(exp_str, '%Y-%m-%d')
                    diff = abs((exp_date - target_date).days)
                    if diff < min_diff:
                        min_diff = diff
                        closest_exp = exp_str
                
                if closest_exp and closest_exp not in target_expirations:
                    target_expirations.append(closest_exp)
            
            risk_free_rate = self.get_risk_free_rate()
            result = {
                'ticker': ticker,
                'current_price': current_price,
                'risk_free_rate': risk_free_rate,
                'expirations': {}
            }
            
            for exp_date in target_expirations:
                try:
                    option_chain = stock.option_chain(exp_date)
                    exp_datetime = datetime.strptime(exp_date, '%Y-%m-%d')
                    days_to_expiry = (exp_datetime - current_date).days
                    time_to_expiry = days_to_expiry / 365.0
                    
                    calls_data = []
                    puts_data = []
                    
                    # Process calls
                    for _, call in option_chain.calls.iterrows():
                        iv = call.get('impliedVolatility', 0)
                        if pd.isna(iv):
                            iv = 0
                        
                        greeks = self.calculate_greeks(
                            current_price, call['strike'], time_to_expiry, 
                            risk_free_rate, iv, 'call'
                        )
                        
                        call_data = {
                            'strike': call['strike'],
                            'lastPrice': call.get('lastPrice', 0),
                            'bid': call.get('bid', 0),
                            'ask': call.get('ask', 0),
                            'volume': call.get('volume', 0),
                            'openInterest': call.get('openInterest', 0),
                            'impliedVolatility': iv,
                            'delta': greeks['delta'],
                            'gamma': greeks['gamma'],
                            'theta': greeks['theta'],
                            'vega': greeks['vega'],
                            'moneyness': abs(call['strike'] - current_price)
                        }
                        calls_data.append(call_data)
                    
                    # Process puts
                    for _, put in option_chain.puts.iterrows():
                        iv = put.get('impliedVolatility', 0)
                        if pd.isna(iv):
                            iv = 0
                        
                        greeks = self.calculate_greeks(
                            current_price, put['strike'], time_to_expiry, 
                            risk_free_rate, iv, 'put'
                        )
                        
                        put_data = {
                            'strike': put['strike'],
                            'lastPrice': put.get('lastPrice', 0),
                            'bid': put.get('bid', 0),
                            'ask': put.get('ask', 0),
                            'volume': put.get('volume', 0),
                            'openInterest': put.get('openInterest', 0),
                            'impliedVolatility': iv,
                            'delta': greeks['delta'],
                            'gamma': greeks['gamma'],
                            'theta': greeks['theta'],
                            'vega': greeks['vega'],
                            'moneyness': abs(put['strike'] - current_price)
                        }
                        puts_data.append(put_data)
                    
                    result['expirations'][exp_date] = {
                        'days_to_expiry': days_to_expiry,
                        'calls': calls_data,
                        'puts': puts_data
                    }
                    
                except Exception as e:
                    print(f"Error processing {exp_date}: {e}")
                    continue
            
            # Cache the result
            self.data_cache[cache_key] = result
            self.cache_timestamp[cache_key] = time.time()
            
            return result
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None

# Initialize Flask app
app = Flask(__name__)
CORS(app)
analyzer = OptionsAnalyzer()

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
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .input-section {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }
        
        .input-group {
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .input-group label {
            font-weight: 600;
            color: #2c3e50;
        }
        
        .input-group input {
            flex: 1;
            min-width: 300px;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .input-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .filters-section {
            padding: 20px 30px;
            background: #f1f3f4;
            border-bottom: 1px solid #e9ecef;
        }
        
        .filters-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .filter-group label {
            font-weight: 600;
            color: #2c3e50;
            font-size: 14px;
        }
        
        .filter-group input, .filter-group select {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        
        .filter-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .btn-secondary {
            background: linear-gradient(135deg, #95a5a6 0%, #7f8c8d 100%);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: transform 0.2s;
        }
        
        .btn-secondary:hover {
            transform: translateY(-1px);
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 18px;
            color: #666;
        }
        
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            margin: 20px;
            border-radius: 8px;
            border: 1px solid #f5c6cb;
        }
        
        .ticker-section {
            margin: 30px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .ticker-header {
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .ticker-name {
            font-size: 1.5em;
            font-weight: bold;
        }
        
        .current-price {
            font-size: 1.3em;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
        }
        
        .expiration-section {
            border-bottom: 1px solid #e9ecef;
        }
        
        .expiration-header {
            background: #ecf0f1;
            padding: 15px 20px;
            font-weight: 600;
            color: #2c3e50;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .options-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
        }
        
        .options-type {
            padding: 20px;
        }
        
        .options-type h4 {
            color: #2c3e50;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }
        
        .calls-section {
            border-right: 1px solid #e9ecef;
        }
        
        .options-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        
        .options-table th {
            background: #34495e;
            color: white;
            padding: 8px 4px;
            text-align: center;
            font-weight: 600;
            font-size: 11px;
        }
        
        .options-table td {
            padding: 6px 4px;
            text-align: center;
            border-bottom: 1px solid #e9ecef;
        }
        
        .options-table tr:hover {
            background: #f8f9fa;
        }
        
        .atm-option {
            background: #fff3cd !important;
            font-weight: bold;
        }
        
        .notes-section {
            margin: 30px;
            background: #e8f4f8;
            border-radius: 10px;
            padding: 25px;
            border-left: 5px solid #3498db;
        }
        
        .notes-section h3 {
            color: #2c3e50;
            margin-bottom: 15px;
        }
        
        .greeks-explanation {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .greek-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .greek-item h4 {
            color: #3498db;
            margin-bottom: 8px;
        }
        
        .conservative-notes {
            background: #d1ecf1;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #bee5eb;
        }
        
        .conservative-notes h4 {
            color: #0c5460;
            margin-bottom: 10px;
        }
        
        @media (max-width: 768px) {
            .options-container {
                grid-template-columns: 1fr;
            }
            
            .calls-section {
                border-right: none;
                border-bottom: 1px solid #e9ecef;
            }
            
            .input-group {
                flex-direction: column;
                align-items: stretch;
            }
            
            .input-group input {
                min-width: auto;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Stock Options Dashboard</h1>
            <p>Advanced Options Analysis with Greeks and Filtering</p>
        </div>
        
        <div class="input-section">
            <div class="input-group">
                <label for="tickers">Stock Tickers:</label>
                <input type="text" id="tickers" placeholder="Enter comma-separated tickers (e.g., AAPL, MSFT, TSLA)" value="AAPL, MSFT">
                <button class="btn" onclick="fetchData()">Analyze Options</button>
            </div>
        </div>
        
        <div class="filters-section">
            <div class="filters-grid">
                <div class="filter-group">
                    <label for="minDelta">Min Delta:</label>
                    <input type="number" id="minDelta" step="0.01" value="-1" min="-1" max="1">
                </div>
                <div class="filter-group">
                    <label for="maxDelta">Max Delta:</label>
                    <input type="number" id="maxDelta" step="0.01" value="1" min="-1" max="1">
                </div>
                <div class="filter-group">
                    <label for="minGamma">Min Gamma:</label>
                    <input type="number" id="minGamma" step="0.001" value="0">
                </div>
                <div class="filter-group">
                    <label for="maxGamma">Max Gamma:</label>
                    <input type="number" id="maxGamma" step="0.001" value="1">
                </div>
                <div class="filter-group">
                    <label for="minTheta">Min Theta:</label>
                    <input type="number" id="minTheta" step="0.01" value="-10">
                </div>
                <div class="filter-group">
                    <label for="maxTheta">Max Theta:</label>
                    <input type="number" id="maxTheta" step="0.01" value="10">
                </div>
                <div class="filter-group">
                    <label for="minVega">Min Vega:</label>
                    <input type="number" id="minVega" step="0.01" value="0">
                </div>
                <div class="filter-group">
                    <label for="maxVega">Max Vega:</label>
                    <input type="number" id="maxVega" step="0.01" value="10">
                </div>
                <div class="filter-group">
                    <label for="minVolume">Min Volume:</label>
                    <input type="number" id="minVolume" value="0">
                </div>
                <div class="filter-group">
                    <label for="minOpenInterest">Min Open Interest:</label>
                    <input type="number" id="minOpenInterest" value="0">
                </div>
                <div class="filter-group">
                    <label for="atmFilter">ATM Filter:</label>
                    <select id="atmFilter">
                        <option value="all">All Strikes</option>
                        <option value="atm">±3 Strikes from ATM</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label for="daysFilter">Days to Expiration:</label>
                    <select id="daysFilter">
                        <option value="all">All Expirations</option>
                        <option value="30">≤ 30 days</option>
                        <option value="60">≤ 60 days</option>
                        <option value="90">≤ 90 days</option>
                        <option value="120">≤ 120 days</option>
                    </select>
                </div>
            </div>
            
            <div class="filter-buttons">
                <button class="btn-secondary" onclick="setConservativeFilters()">Conservative Defaults</button>
                <button class="btn-secondary" onclick="resetFilters()">Reset Filters</button>
                <button class="btn-secondary" onclick="applyFilters()">Apply Filters</button>
            </div>
        </div>
        
        <div id="loading" class="loading" style="display: none;">
            <p>🔄 Fetching options data...</p>
        </div>
        
        <div id="error" class="error" style="display: none;"></div>
        
        <div id="results"></div>
        
        <div class="notes-section">
            <h3>📚 Options Greeks Explained</h3>
            <div class="greeks-explanation">
                <div class="greek-item">
                    <h4>Delta (Δ)</h4>
                    <p>Measures price sensitivity to underlying stock movement. Call deltas: 0 to 1, Put deltas: -1 to 0. Higher absolute values = more sensitive to stock price changes.</p>
                </div>
                <div class="greek-item">
                    <h4>Gamma (Γ)</h4>
                    <p>Rate of change of delta. Higher gamma = delta changes more rapidly. ATM options typically have highest gamma. Important for delta hedging.</p>
                </div>
                <div class="greek-item">
                    <h4>Theta (Θ)</h4>
                    <p>Time decay per day. Usually negative for long positions. Shows how much option value decreases daily. Accelerates as expiration approaches.</p>
                </div>
                <div class="greek-item">
                    <h4>Vega (ν)</h4>
                    <p>Sensitivity to implied volatility changes. Higher vega = more sensitive to volatility. ATM options and longer-dated options typically have higher vega.</p>
                </div>
            </div>
            
            <div class="conservative-notes">
                <h4>🛡️ Conservative Trading Guidelines</h4>
                <ul>
                    <li><strong>Delta:</strong> 0.3-0.7 for moderate directional exposure</li>
                    <li><strong>Gamma:</strong> 0.01-0.05 to avoid excessive delta swings</li>
                    <li><strong>Theta:</strong> -0.05 to -0.15 for manageable time decay</li>
                    <li><strong>Vega:</strong> 0.05-0.20 to limit volatility risk</li>
                    <li><strong>Volume & OI:</strong> Minimum 50+ for liquidity</li>
                    <li><strong>Time:</strong> 30-90 days to expiration for optimal time decay balance</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        let rawData = {};
        
        function fetchData() {
            const tickers = document.getElementById('tickers').value;
            if (!tickers.trim()) {
                alert('Please enter at least one ticker symbol');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('error').style.display = 'none';
            document.getElementById('results').innerHTML = '';
            
            fetch('/api/options', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    tickers: tickers.split(',').map(t => t.trim().toUpperCase())
                })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                if (data.error) {
                    document.getElementById('error').textContent = data.error;
                    document.getElementById('error').style.display = 'block';
                } else {
                    rawData = data;
                    displayResults(data);
                }
            })
            .catch(error => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').textContent = 'Error fetching data: ' + error.message;
                document.getElementById('error').style.display = 'block';
            });
        }
        
        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '';
            
            Object.keys(data).forEach(ticker => {
                const tickerData = data[ticker];
                if (!tickerData || tickerData.error) {
                    resultsDiv.innerHTML += `
                        <div class="error">
                            Error loading data for ${ticker}: ${tickerData?.error || 'Unknown error'}
                        </div>
                    `;
                    return;
                }
                
                const tickerDiv = document.createElement('div');
                tickerDiv.className = 'ticker-section';
                tickerDiv.innerHTML = `
                    <div class="ticker-header">
                        <div class="ticker-name">${ticker}</div>
                        <div class="current-price">$${tickerData.current_price.toFixed(2)}</div>
                    </div>
                `;
                
                Object.keys(tickerData.expirations).forEach(expDate => {
                    const expData = tickerData.expirations[expDate];
                    const expDiv = document.createElement('div');
                    expDiv.className = 'expiration-section';
                    
                    expDiv.innerHTML = `
                        <div class="expiration-header">
                            <span>Expiration: ${expDate}</span>
                            <span>${expData.days_to_expiry} days to expiry</span>
                        </div>
                        <div class="options-container">
                            <div class="options-type calls-section">
                                <h4>📈 Call Options</h4>
                                ${generateOptionsTable(expData.calls, tickerData.current_price)}
                            </div>
                            <div class="options-type puts-section">
                                <h4>📉 Put Options</h4>
                                ${generateOptionsTable(expData.puts, tickerData.current_price)}
                            </div>
                        </div>
                    `;
                    
                    tickerDiv.appendChild(expDiv);
                });
                
                resultsDiv.appendChild(tickerDiv);
            });
        }
        
        function generateOptionsTable(options, currentPrice) {
            if (!options || options.length === 0) {
                return '<p>No options data available</p>';
            }
            
            let tableHTML = `
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
            
            options.forEach(option => {
                const isATM = Math.abs(option.strike - currentPrice) <= (currentPrice * 0.05);
                const rowClass = isATM ? 'atm-option' : '';
                
                tableHTML += `
                    <tr class="${rowClass}" data-option='${JSON.stringify(option)}'>
                        <td>$${option.strike.toFixed(2)}</td>
                        <td>$${option.lastPrice.toFixed(2)}</td>
                        <td>$${option.bid.toFixed(2)}</td>
                        <td>$${option.ask.toFixed(2)}</td>
                        <td>${option.volume || 0}</td>
                        <td>${option.openInterest || 0}</td>
                        <td>${(option.impliedVolatility * 100).toFixed(1)}%</td>
                        <td>${option.delta.toFixed(3)}</td>
                        <td>${option.gamma.toFixed(3)}</td>
                        <td>${option.theta.toFixed(3)}</td>
                        <td>${option.vega.toFixed(3)}</td>
                    </tr>
                `;
            });
            
            tableHTML += `
                    </tbody>
                </table>
            `;
            
            return tableHTML;
        }
        
        function setConservativeFilters() {
            document.getElementById('minDelta').value = '0.3';
            document.getElementById('maxDelta').value = '0.7';
            document.getElementById('minGamma').value = '0.01';
            document.getElementById('maxGamma').value = '0.05';
            document.getElementById('minTheta').value = '-0.15';
            document.getElementById('maxTheta').value = '-0.05';
            document.getElementById('minVega').value = '0.05';
            document.getElementById('maxVega').value = '0.20';
            document.getElementById('minVolume').value = '50';
            document.getElementById('minOpenInterest').value = '50';
            document.getElementById('atmFilter').value = 'atm';
            document.getElementById('daysFilter').value = '90';
            
            applyFilters();
        }
        
        function resetFilters() {
            document.getElementById('minDelta').value = '-1';
            document.getElementById('maxDelta').value = '1';
            document.getElementById('minGamma').value = '0';
            document.getElementById('maxGamma').value = '1';
            document.getElementById('minTheta').value = '-10';
            document.getElementById('maxTheta').value = '10';
            document.getElementById('minVega').value = '0';
            document.getElementById('maxVega').value = '10';
            document.getElementById('minVolume').value = '0';
            document.getElementById('minOpenInterest').value = '0';
            document.getElementById('atmFilter').value = 'all';
            document.getElementById('daysFilter').value = 'all';
            
            applyFilters();
        }
        
        function applyFilters() {
            if (Object.keys(rawData).length === 0) {
                return;
            }
            
            const filters = {
                minDelta: parseFloat(document.getElementById('minDelta').value),
                maxDelta: parseFloat(document.getElementById('maxDelta').value),
                minGamma: parseFloat(document.getElementById('minGamma').value),
                maxGamma: parseFloat(document.getElementById('maxGamma').value),
                minTheta: parseFloat(document.getElementById('minTheta').value),
                maxTheta: parseFloat(document.getElementById('maxTheta').value),
                minVega: parseFloat(document.getElementById('minVega').value),
                maxVega: parseFloat(document.getElementById('maxVega').value),
                minVolume: parseInt(document.getElementById('minVolume').value),
                minOpenInterest: parseInt(document.getElementById('minOpenInterest').value),
                atmFilter: document.getElementById('atmFilter').value,
                daysFilter: document.getElementById('daysFilter').value
            };
            
            const filteredData = {};
            
            Object.keys(rawData).forEach(ticker => {
                const tickerData = rawData[ticker];
                if (!tickerData || tickerData.error) {
                    filteredData[ticker] = tickerData;
                    return;
                }
                
                filteredData[ticker] = {
                    ...tickerData,
                    expirations: {}
                };
                
                Object.keys(tickerData.expirations).forEach(expDate => {
                    const expData = tickerData.expirations[expDate];
                    
                    // Filter by days to expiration
                    if (filters.daysFilter !== 'all' && expData.days_to_expiry > parseInt(filters.daysFilter)) {
                        return;
                    }
                    
                    const filteredCalls = expData.calls.filter(option => filterOption(option, filters, tickerData.current_price));
                    const filteredPuts = expData.puts.filter(option => filterOption(option, filters, tickerData.current_price));
                    
                    if (filteredCalls.length > 0 || filteredPuts.length > 0) {
                        filteredData[ticker].expirations[expDate] = {
                            ...expData,
                            calls: filteredCalls,
                            puts: filteredPuts
                        };
                    }
                });
            });
            
            displayResults(filteredData);
        }
        
        function filterOption(option, filters, currentPrice) {
            // ATM filter
            if (filters.atmFilter === 'atm') {
                const strikeCount = 3;
                const priceRange = currentPrice * 0.1; // 10% range
                if (Math.abs(option.strike - currentPrice) > priceRange) {
                    return false;
                }
            }
            
            // Greeks filters
            if (option.delta < filters.minDelta || option.delta > filters.maxDelta) return false;
            if (option.gamma < filters.minGamma || option.gamma > filters.maxGamma) return false;
            if (option.theta < filters.minTheta || option.theta > filters.maxTheta) return false;
            if (option.vega < filters.minVega || option.vega > filters.maxVega) return false;
            
            // Volume and Open Interest filters
            if ((option.volume || 0) < filters.minVolume) return false;
            if ((option.openInterest || 0) < filters.minOpenInterest) return false;
            
            return true;
        }
        
        // Auto-fetch data on page load with default tickers
        window.onload = function() {
            // You can uncomment the line below to auto-fetch data on load
            // fetchData();
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/options', methods=['POST'])
def get_options():
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({'error': 'No tickers provided'})
        
        results = {}
        for ticker in tickers:
            ticker = ticker.strip().upper()
            if ticker:
                print(f"Fetching data for {ticker}...")
                options_data = analyzer.get_options_data(ticker)
                if options_data:
                    results[ticker] = options_data
                else:
                    results[ticker] = {'error': f'Could not fetch data for {ticker}'}
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)})

def run_flask_app():
    """Run Flask app in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def setup_ngrok_auth():
    """Help users setup ngrok authentication"""
    print("🔐 Setting up ngrok authentication...")
    print("📝 To use ngrok, you need a free account and auth token:")
    print("   1. Sign up at: https://ngrok.com")
    print("   2. Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken")
    print("   3. Run this command to set your auth token:")
    print("      !ngrok authtoken YOUR_TOKEN_HERE")
    print("   4. Or set it programmatically (uncomment the line below in the code)")
    print("      # ngrok.set_auth_token('YOUR_TOKEN_HERE')")

def setup_ngrok():
    """Setup ngrok tunnel"""
    try:
        # Kill any existing ngrok processes
        ngrok.kill()
        
        # Uncomment the line below and add your ngrok auth token if needed
        # ngrok.set_auth_token("YOUR_NGROK_AUTH_TOKEN_HERE")
        
        # Create tunnel to Flask app with custom options
        public_tunnel = ngrok.connect(
            5000,
            proto="http",
            options={"bind_tls": True}  # Force HTTPS
        )
        public_url = public_tunnel.public_url
        
        print(f"🌐 ngrok tunnel established!")
        print(f"🔗 Public URL: {public_url}")
        print(f"🔗 Local URL: http://localhost:5000")
        print(f"📊 ngrok Web Interface: http://localhost:4040")
        
        return public_url
        
    except Exception as e:
        error_msg = str(e).lower()
        print(f"⚠️  ngrok setup failed: {e}")
        
        if "authtoken" in error_msg or "authentication" in error_msg:
            print("\n🔐 Authentication Required:")
            setup_ngrok_auth()
        else:
            print("💡 This might be due to:")
            print("   • Network restrictions")
            print("   • ngrok service unavailable")
            print("   • Port already in use")
        
        print("📋 You can still access the dashboard locally at: http://localhost:5000")
        return None

def main():
    """Main function to run the application"""
    print("🚀 Starting Stock Options Dashboard...")
    print("📦 Installing required packages...")
    
    # Start Flask app in background thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # Wait a moment for Flask to start
    time.sleep(3)
    
    # Setup ngrok tunnel
    print("\n🔗 Setting up ngrok tunnel...")
    public_url = setup_ngrok()
    
    print("\n" + "="*60)
    print("✅ Stock Options Dashboard is running!")
    print("="*60)
    
    if public_url:
        print(f"🌍 Public Access: {public_url}")
        print(f"🏠 Local Access: http://localhost:5000")
        print("\n💡 Share the public URL with anyone to access your dashboard!")
    else:
        print("🏠 Local Access: http://localhost:5000")
        print("💡 If you need public access, you can manually setup ngrok")
    
    print("\n📋 Features available:")
    print("   • Interactive options data for multiple tickers")
    print("   • Complete Greeks calculations (Delta, Gamma, Theta, Vega)")
    print("   • Advanced filtering system")
    print("   • At-the-money (ATM) filtering")
    print("   • Days to expiration filtering")
    print("   • Conservative trading presets")
    print("   • Educational content about Greeks")
    print("\n🎯 Default tickers: AAPL, MSFT (you can change these)")
    print("📚 Click 'Conservative Defaults' for safe trading parameters")
    print("\n⚠️  Note: This will run until you stop the cell execution")
    print("="*60)
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
        print("🔄 Cleaning up ngrok tunnel...")
        try:
            ngrok.kill()
            print("✅ ngrok tunnel closed")
        except:
            pass

if __name__ == "__main__":
    main()