#!/usr/bin/env python3
"""
Interactive Stock Options Dashboard for Google Colab
A comprehensive Flask web application for analyzing live options data with Greeks
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
        'threading',
        'flask-cors'
    ]
    
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Install packages first
install_packages()

# Import all required libraries
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import threading
import time
import json
import warnings
warnings.filterwarnings('ignore')

class OptionsAnalyzer:
    def __init__(self):
        self.data_cache = {}
        self.last_update = {}
    
    def get_stock_price(self, ticker):
        """Get current stock price"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            return hist['Close'].iloc[-1] if not hist.empty else None
        except:
            return None
    
    def calculate_greeks(self, S, K, T, r, sigma, option_type='call'):
        """Calculate Black-Scholes Greeks"""
        if T <= 0 or sigma <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
        
        try:
            d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
            d2 = d1 - sigma*np.sqrt(T)
            
            if option_type == 'call':
                delta = norm.cdf(d1)
                theta = (-S*norm.pdf(d1)*sigma/(2*np.sqrt(T)) - 
                        r*K*np.exp(-r*T)*norm.cdf(d2)) / 365
            else:
                delta = norm.cdf(d1) - 1
                theta = (-S*norm.pdf(d1)*sigma/(2*np.sqrt(T)) + 
                        r*K*np.exp(-r*T)*norm.cdf(-d2)) / 365
            
            gamma = norm.pdf(d1) / (S*sigma*np.sqrt(T))
            vega = S*norm.pdf(d1)*np.sqrt(T) / 100
            
            return {
                'delta': round(delta, 4),
                'gamma': round(gamma, 4),
                'theta': round(theta, 4),
                'vega': round(vega, 4)
            }
        except:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
    
    def get_target_dates(self, days_list=[90, 120, 150]):
        """Get target expiration dates"""
        today = datetime.now()
        target_dates = []
        for days in days_list:
            target_date = today + timedelta(days=days)
            target_dates.append(target_date)
        return target_dates
    
    def find_closest_expiration(self, available_dates, target_date):
        """Find the closest available expiration date to target"""
        if not available_dates:
            return None
        
        target_timestamp = target_date.timestamp()
        closest_date = min(available_dates, 
                          key=lambda x: abs(x.timestamp() - target_timestamp))
        return closest_date
    
    def get_options_data(self, ticker):
        """Fetch options data for a ticker"""
        try:
            stock = yf.Ticker(ticker)
            current_price = self.get_stock_price(ticker)
            
            if not current_price:
                return None
            
            # Get available expiration dates
            expirations = stock.options
            if not expirations:
                return None
            
            # Convert to datetime objects
            exp_dates = [datetime.strptime(exp, '%Y-%m-%d') for exp in expirations]
            
            # Find target dates (90, 120, 150 days)
            target_dates = self.get_target_dates()
            selected_expirations = []
            
            for target in target_dates:
                closest = self.find_closest_expiration(exp_dates, target)
                if closest and closest not in selected_expirations:
                    selected_expirations.append(closest)
            
            options_data = []
            risk_free_rate = 0.05  # Approximate risk-free rate
            
            for exp_date in selected_expirations:
                exp_str = exp_date.strftime('%Y-%m-%d')
                days_to_exp = (exp_date - datetime.now()).days
                time_to_exp = days_to_exp / 365.0
                
                try:
                    # Get options chain
                    opt_chain = stock.option_chain(exp_str)
                    calls = opt_chain.calls
                    puts = opt_chain.puts
                    
                    # Process calls
                    for _, call in calls.iterrows():
                        iv = call.get('impliedVolatility', 0)
                        if iv > 0:
                            greeks = self.calculate_greeks(
                                current_price, call['strike'], time_to_exp, 
                                risk_free_rate, iv, 'call'
                            )
                        else:
                            greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
                        
                        options_data.append({
                            'ticker': ticker,
                            'type': 'Call',
                            'expiration': exp_str,
                            'days_to_exp': days_to_exp,
                            'strike': call['strike'],
                            'lastPrice': call.get('lastPrice', 0),
                            'bid': call.get('bid', 0),
                            'ask': call.get('ask', 0),
                            'volume': call.get('volume', 0),
                            'openInterest': call.get('openInterest', 0),
                            'impliedVolatility': round(iv * 100, 2),
                            'delta': greeks['delta'],
                            'gamma': greeks['gamma'],
                            'theta': greeks['theta'],
                            'vega': greeks['vega'],
                            'current_price': current_price
                        })
                    
                    # Process puts
                    for _, put in puts.iterrows():
                        iv = put.get('impliedVolatility', 0)
                        if iv > 0:
                            greeks = self.calculate_greeks(
                                current_price, put['strike'], time_to_exp, 
                                risk_free_rate, iv, 'put'
                            )
                        else:
                            greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
                        
                        options_data.append({
                            'ticker': ticker,
                            'type': 'Put',
                            'expiration': exp_str,
                            'days_to_exp': days_to_exp,
                            'strike': put['strike'],
                            'lastPrice': put.get('lastPrice', 0),
                            'bid': put.get('bid', 0),
                            'ask': put.get('ask', 0),
                            'volume': put.get('volume', 0),
                            'openInterest': put.get('openInterest', 0),
                            'impliedVolatility': round(iv * 100, 2),
                            'delta': greeks['delta'],
                            'gamma': greeks['gamma'],
                            'theta': greeks['theta'],
                            'vega': greeks['vega'],
                            'current_price': current_price
                        })
                
                except Exception as e:
                    print(f"Error processing {ticker} {exp_str}: {e}")
                    continue
            
            return options_data
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None

# Initialize Flask app
app = Flask(__name__)
CORS(app)
analyzer = OptionsAnalyzer()

# HTML template for the dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Options Dashboard</title>
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
        
        .controls {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        
        .input-group {
            margin-bottom: 20px;
        }
        
        .input-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .input-group input, .input-group select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        .input-group input:focus, .input-group select:focus {
            outline: none;
            border-color: #3498db;
        }
        
        .filters {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .filter-group {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .filter-group h3 {
            margin-bottom: 15px;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 5px;
        }
        
        .button {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s, box-shadow 0.2s;
            margin: 5px;
        }
        
        .button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(52, 152, 219, 0.3);
        }
        
        .button.secondary {
            background: linear-gradient(135deg, #95a5a6, #7f8c8d);
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 18px;
            color: #7f8c8d;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .summary {
            background: #e8f5e8;
            border: 2px solid #27ae60;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        
        .summary h3 {
            color: #27ae60;
            margin-bottom: 15px;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }
        
        .summary-item {
            text-align: center;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .summary-item .value {
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .summary-item .label {
            font-size: 0.9em;
            color: #7f8c8d;
            margin-top: 5px;
        }
        
        .ticker-section {
            margin: 30px 0;
            border: 2px solid #ddd;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .ticker-header {
            background: linear-gradient(135deg, #34495e, #2c3e50);
            color: white;
            padding: 20px;
            font-size: 1.3em;
            font-weight: bold;
        }
        
        .expiration-section {
            margin: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .expiration-header {
            background: #3498db;
            color: white;
            padding: 15px;
            font-weight: bold;
        }
        
        .options-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        .options-table th {
            background: #f8f9fa;
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
            font-size: 0.9em;
        }
        
        .options-table td {
            padding: 10px 8px;
            text-align: center;
            border-bottom: 1px solid #dee2e6;
            font-size: 0.85em;
        }
        
        .options-table tr:hover {
            background: #f8f9fa;
        }
        
        .call-row {
            background: rgba(46, 204, 113, 0.1);
        }
        
        .put-row {
            background: rgba(231, 76, 60, 0.1);
        }
        
        .atm-highlight {
            background: rgba(241, 196, 15, 0.3) !important;
            font-weight: bold;
        }
        
        .notes {
            background: #fff3cd;
            border: 2px solid #ffeaa7;
            border-radius: 10px;
            padding: 25px;
            margin: 30px 0;
        }
        
        .notes h3 {
            color: #f39c12;
            margin-bottom: 20px;
            font-size: 1.4em;
        }
        
        .notes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .note-item {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .note-item h4 {
            color: #e67e22;
            margin-bottom: 10px;
        }
        
        .note-item p {
            line-height: 1.6;
            color: #2c3e50;
        }
        
        .conservative-values {
            background: #d5f4e6;
            border: 2px solid #27ae60;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .conservative-values h5 {
            color: #27ae60;
            margin-bottom: 10px;
        }
        
        @media (max-width: 768px) {
            .filters {
                grid-template-columns: 1fr;
            }
            
            .options-table {
                font-size: 0.7em;
            }
            
            .options-table th,
            .options-table td {
                padding: 6px 4px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Interactive Options Dashboard</h1>
            <p>Live Stock Options Analysis with Greeks & Advanced Filtering</p>
        </div>
        
        <div class="controls">
            <div class="input-group">
                <label for="tickers">Stock Ticker Symbols (comma-separated):</label>
                <input type="text" id="tickers" placeholder="e.g., AAPL, MSFT, TSLA, GOOGL" value="AAPL, MSFT">
            </div>
            
            <div class="filters">
                <div class="filter-group">
                    <h3>🎯 Greeks Filters</h3>
                    <label>Delta Range:</label>
                    <input type="number" id="deltaMin" placeholder="Min" step="0.01" value="">
                    <input type="number" id="deltaMax" placeholder="Max" step="0.01" value="">
                    
                    <label>Gamma Range:</label>
                    <input type="number" id="gammaMin" placeholder="Min" step="0.0001" value="">
                    <input type="number" id="gammaMax" placeholder="Max" step="0.0001" value="">
                    
                    <label>Theta Range:</label>
                    <input type="number" id="thetaMin" placeholder="Min" step="0.01" value="">
                    <input type="number" id="thetaMax" placeholder="Max" step="0.01" value="">
                    
                    <label>Vega Range:</label>
                    <input type="number" id="vegaMin" placeholder="Min" step="0.01" value="">
                    <input type="number" id="vegaMax" placeholder="Max" step="0.01" value="">
                </div>
                
                <div class="filter-group">
                    <h3>📅 Time & Price Filters</h3>
                    <label>Days to Expiration:</label>
                    <input type="number" id="daysMin" placeholder="Min Days" value="">
                    <input type="number" id="daysMax" placeholder="Max Days" value="">
                    
                    <label>Implied Volatility (%):</label>
                    <input type="number" id="ivMin" placeholder="Min IV" step="0.1" value="">
                    <input type="number" id="ivMax" placeholder="Max IV" step="0.1" value="">
                    
                    <label>Volume:</label>
                    <input type="number" id="volumeMin" placeholder="Min Volume" value="">
                </div>
                
                <div class="filter-group">
                    <h3>⚙️ Options</h3>
                    <label>
                        <input type="checkbox" id="atmOnly"> At The Money Only (±3 strikes)
                    </label>
                    <br><br>
                    <label>Option Type:</label>
                    <select id="optionType">
                        <option value="both">Both Calls & Puts</option>
                        <option value="calls">Calls Only</option>
                        <option value="puts">Puts Only</option>
                    </select>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <button class="button" onclick="loadData()">🔄 Load Options Data</button>
                <button class="button secondary" onclick="setConservativeDefaults()">🛡️ Conservative Defaults</button>
                <button class="button secondary" onclick="clearFilters()">🧹 Clear Filters</button>
            </div>
        </div>
        
        <div id="results"></div>
        
        <div class="notes">
            <h3>📚 Educational Notes</h3>
            <div class="notes-grid">
                <div class="note-item">
                    <h4>Delta (Δ)</h4>
                    <p>Measures the rate of change of option price with respect to the underlying stock price. For calls: 0 to 1, for puts: -1 to 0. Higher absolute delta means more price sensitivity.</p>
                </div>
                
                <div class="note-item">
                    <h4>Gamma (Γ)</h4>
                    <p>Measures the rate of change of delta with respect to the underlying price. Higher gamma means delta changes more rapidly. ATM options have highest gamma.</p>
                </div>
                
                <div class="note-item">
                    <h4>Theta (Θ)</h4>
                    <p>Measures time decay - how much option value decreases per day. Always negative for long positions. Options lose value faster as expiration approaches.</p>
                </div>
                
                <div class="note-item">
                    <h4>Vega (ν)</h4>
                    <p>Measures sensitivity to implied volatility changes. Higher vega means option price is more sensitive to volatility changes. ATM options have highest vega.</p>
                </div>
            </div>
            
            <div class="conservative-values">
                <h5>🛡️ Conservative Trading Guidelines:</h5>
                <ul>
                    <li><strong>Delta:</strong> 0.3-0.7 for moderate directional exposure</li>
                    <li><strong>Gamma:</strong> Below 0.05 for manageable delta risk</li>
                    <li><strong>Theta:</strong> Above -0.1 to limit time decay</li>
                    <li><strong>Vega:</strong> Below 0.2 to reduce volatility risk</li>
                    <li><strong>Volume:</strong> Above 50 for adequate liquidity</li>
                    <li><strong>Days to Expiration:</strong> 30-90 days for balance of time and premium</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        let allData = [];
        
        function loadData() {
            const tickers = document.getElementById('tickers').value.trim();
            if (!tickers) {
                alert('Please enter at least one ticker symbol');
                return;
            }
            
            document.getElementById('results').innerHTML = `
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Loading options data for: ${tickers}</p>
                    <p>This may take a moment...</p>
                </div>
            `;
            
            fetch('/api/options', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({tickers: tickers})
            })
            .then(response => response.json())
            .then(data => {
                allData = data;
                displayData(data);
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('results').innerHTML = `
                    <div class="loading">
                        <p style="color: #e74c3c;">Error loading data: ${error.message}</p>
                    </div>
                `;
            });
        }
        
        function applyFilters() {
            if (allData.length === 0) return;
            
            const filters = {
                deltaMin: parseFloat(document.getElementById('deltaMin').value) || null,
                deltaMax: parseFloat(document.getElementById('deltaMax').value) || null,
                gammaMin: parseFloat(document.getElementById('gammaMin').value) || null,
                gammaMax: parseFloat(document.getElementById('gammaMax').value) || null,
                thetaMin: parseFloat(document.getElementById('thetaMin').value) || null,
                thetaMax: parseFloat(document.getElementById('thetaMax').value) || null,
                vegaMin: parseFloat(document.getElementById('vegaMin').value) || null,
                vegaMax: parseFloat(document.getElementById('vegaMax').value) || null,
                daysMin: parseInt(document.getElementById('daysMin').value) || null,
                daysMax: parseInt(document.getElementById('daysMax').value) || null,
                ivMin: parseFloat(document.getElementById('ivMin').value) || null,
                ivMax: parseFloat(document.getElementById('ivMax').value) || null,
                volumeMin: parseInt(document.getElementById('volumeMin').value) || null,
                atmOnly: document.getElementById('atmOnly').checked,
                optionType: document.getElementById('optionType').value
            };
            
            const filteredData = allData.filter(option => {
                // Greeks filters
                if (filters.deltaMin !== null && Math.abs(option.delta) < filters.deltaMin) return false;
                if (filters.deltaMax !== null && Math.abs(option.delta) > filters.deltaMax) return false;
                if (filters.gammaMin !== null && option.gamma < filters.gammaMin) return false;
                if (filters.gammaMax !== null && option.gamma > filters.gammaMax) return false;
                if (filters.thetaMin !== null && option.theta < filters.thetaMin) return false;
                if (filters.thetaMax !== null && option.theta > filters.thetaMax) return false;
                if (filters.vegaMin !== null && option.vega < filters.vegaMin) return false;
                if (filters.vegaMax !== null && option.vega > filters.vegaMax) return false;
                
                // Time and price filters
                if (filters.daysMin !== null && option.days_to_exp < filters.daysMin) return false;
                if (filters.daysMax !== null && option.days_to_exp > filters.daysMax) return false;
                if (filters.ivMin !== null && option.impliedVolatility < filters.ivMin) return false;
                if (filters.ivMax !== null && option.impliedVolatility > filters.ivMax) return false;
                if (filters.volumeMin !== null && option.volume < filters.volumeMin) return false;
                
                // ATM filter
                if (filters.atmOnly) {
                    const priceDiff = Math.abs(option.strike - option.current_price);
                    const atmThreshold = option.current_price * 0.05; // 5% threshold
                    if (priceDiff > atmThreshold) return false;
                }
                
                // Option type filter
                if (filters.optionType === 'calls' && option.type !== 'Call') return false;
                if (filters.optionType === 'puts' && option.type !== 'Put') return false;
                
                return true;
            });
            
            displayData(filteredData);
        }
        
        function displayData(data) {
            if (data.length === 0) {
                document.getElementById('results').innerHTML = `
                    <div class="loading">
                        <p>No options data found matching your criteria.</p>
                    </div>
                `;
                return;
            }
            
            // Calculate summary statistics
            const summary = calculateSummary(data);
            
            // Group data by ticker and expiration
            const groupedData = {};
            data.forEach(option => {
                if (!groupedData[option.ticker]) {
                    groupedData[option.ticker] = {};
                }
                if (!groupedData[option.ticker][option.expiration]) {
                    groupedData[option.ticker][option.expiration] = [];
                }
                groupedData[option.ticker][option.expiration].push(option);
            });
            
            let html = '';
            
            // Add summary
            if (data.length > 1) {
                html += `
                    <div class="summary">
                        <h3>📊 Summary Statistics (${data.length} options)</h3>
                        <div class="summary-grid">
                            <div class="summary-item">
                                <div class="value">${summary.avgDelta}</div>
                                <div class="label">Avg Delta</div>
                            </div>
                            <div class="summary-item">
                                <div class="value">${summary.avgGamma}</div>
                                <div class="label">Avg Gamma</div>
                            </div>
                            <div class="summary-item">
                                <div class="value">${summary.avgTheta}</div>
                                <div class="label">Avg Theta</div>
                            </div>
                            <div class="summary-item">
                                <div class="value">${summary.avgVega}</div>
                                <div class="label">Avg Vega</div>
                            </div>
                            <div class="summary-item">
                                <div class="value">${summary.avgIV}%</div>
                                <div class="label">Avg IV</div>
                            </div>
                            <div class="summary-item">
                                <div class="value">${summary.totalVolume}</div>
                                <div class="label">Total Volume</div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Display grouped data
            for (const ticker in groupedData) {
                html += `<div class="ticker-section">`;
                html += `<div class="ticker-header">${ticker} - Current Price: $${groupedData[ticker][Object.keys(groupedData[ticker])[0]][0].current_price.toFixed(2)}</div>`;
                
                for (const expiration in groupedData[ticker]) {
                    const options = groupedData[ticker][expiration];
                    const daysToExp = options[0].days_to_exp;
                    
                    html += `<div class="expiration-section">`;
                    html += `<div class="expiration-header">Expiration: ${expiration} (${daysToExp} days)</div>`;
                    
                    html += `
                        <table class="options-table">
                            <thead>
                                <tr>
                                    <th>Type</th>
                                    <th>Strike</th>
                                    <th>Last</th>
                                    <th>Bid</th>
                                    <th>Ask</th>
                                    <th>Volume</th>
                                    <th>OI</th>
                                    <th>IV%</th>
                                    <th>Delta</th>
                                    <th>Gamma</th>
                                    <th>Theta</th>
                                    <th>Vega</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    
                    // Sort options by strike price
                    options.sort((a, b) => a.strike - b.strike);
                    
                    options.forEach(option => {
                        const isATM = Math.abs(option.strike - option.current_price) <= (option.current_price * 0.05);
                        const rowClass = option.type === 'Call' ? 'call-row' : 'put-row';
                        const atmClass = isATM ? 'atm-highlight' : '';
                        
                        html += `
                            <tr class="${rowClass} ${atmClass}">
                                <td>${option.type}</td>
                                <td>$${option.strike.toFixed(2)}</td>
                                <td>$${option.lastPrice.toFixed(2)}</td>
                                <td>$${option.bid.toFixed(2)}</td>
                                <td>$${option.ask.toFixed(2)}</td>
                                <td>${option.volume}</td>
                                <td>${option.openInterest}</td>
                                <td>${option.impliedVolatility.toFixed(1)}%</td>
                                <td>${option.delta.toFixed(3)}</td>
                                <td>${option.gamma.toFixed(4)}</td>
                                <td>${option.theta.toFixed(3)}</td>
                                <td>${option.vega.toFixed(3)}</td>
                            </tr>
                        `;
                    });
                    
                    html += `</tbody></table></div>`;
                }
                
                html += `</div>`;
            }
            
            document.getElementById('results').innerHTML = html;
        }
        
        function calculateSummary(data) {
            if (data.length === 0) return {};
            
            const sums = data.reduce((acc, option) => {
                acc.delta += Math.abs(option.delta);
                acc.gamma += option.gamma;
                acc.theta += option.theta;
                acc.vega += option.vega;
                acc.iv += option.impliedVolatility;
                acc.volume += option.volume;
                return acc;
            }, {delta: 0, gamma: 0, theta: 0, vega: 0, iv: 0, volume: 0});
            
            return {
                avgDelta: (sums.delta / data.length).toFixed(3),
                avgGamma: (sums.gamma / data.length).toFixed(4),
                avgTheta: (sums.theta / data.length).toFixed(3),
                avgVega: (sums.vega / data.length).toFixed(3),
                avgIV: (sums.iv / data.length).toFixed(1),
                totalVolume: sums.volume.toLocaleString()
            };
        }
        
        function setConservativeDefaults() {
            document.getElementById('deltaMin').value = '0.3';
            document.getElementById('deltaMax').value = '0.7';
            document.getElementById('gammaMax').value = '0.05';
            document.getElementById('thetaMin').value = '-0.1';
            document.getElementById('vegaMax').value = '0.2';
            document.getElementById('daysMin').value = '30';
            document.getElementById('daysMax').value = '90';
            document.getElementById('volumeMin').value = '50';
            applyFilters();
        }
        
        function clearFilters() {
            document.querySelectorAll('input[type="number"]').forEach(input => input.value = '');
            document.getElementById('atmOnly').checked = false;
            document.getElementById('optionType').value = 'both';
            displayData(allData);
        }
        
        // Add event listeners for real-time filtering
        document.addEventListener('DOMContentLoaded', function() {
            const filterInputs = document.querySelectorAll('input, select');
            filterInputs.forEach(input => {
                input.addEventListener('change', applyFilters);
                if (input.type === 'number' || input.type === 'text') {
                    input.addEventListener('input', debounce(applyFilters, 500));
                }
            });
        });
        
        function debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
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
        tickers_input = data.get('tickers', '')
        
        # Parse tickers
        tickers = [ticker.strip().upper() for ticker in tickers_input.split(',') if ticker.strip()]
        
        if not tickers:
            return jsonify({'error': 'No valid tickers provided'}), 400
        
        all_options = []
        
        for ticker in tickers:
            print(f"Fetching data for {ticker}...")
            options_data = analyzer.get_options_data(ticker)
            if options_data:
                all_options.extend(options_data)
            else:
                print(f"No data found for {ticker}")
        
        return jsonify(all_options)
        
    except Exception as e:
        print(f"Error in API: {e}")
        return jsonify({'error': str(e)}), 500

def run_flask_app():
    """Run Flask app in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    """Main function to run the dashboard"""
    print("🚀 Starting Interactive Options Dashboard...")
    print("📊 This dashboard provides comprehensive options analysis with:")
    print("   • Live options data for multiple tickers")
    print("   • Complete Greeks calculation (Delta, Gamma, Theta, Vega)")
    print("   • Advanced filtering capabilities")
    print("   • At-the-money options highlighting")
    print("   • Conservative trading guidelines")
    print("   • Summary statistics")
    print()
    
    # Start Flask app in background thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # Wait for server to start
    time.sleep(3)
    
    print("✅ Dashboard is running!")
    print("🌐 Access your dashboard at: http://localhost:5000")
    print()
    print("📝 Instructions:")
    print("1. Enter comma-separated ticker symbols (e.g., AAPL, MSFT, TSLA)")
    print("2. Click 'Load Options Data' to fetch live data")
    print("3. Use filters to narrow down options based on Greeks, volume, etc.")
    print("4. Click 'Conservative Defaults' for safe trading parameters")
    print("5. Enable 'At The Money Only' to focus on ATM options")
    print()
    print("💡 Educational notes are included at the bottom of the dashboard!")
    print()
    print("⚠️  Note: This is for educational purposes. Always consult with a financial advisor.")
    print()
    
    # For Colab, we need to use ngrok or similar to expose the port
    try:
        # Try to install and use pyngrok for Colab
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])
        from pyngrok import ngrok
        
        # Create tunnel
        public_url = ngrok.connect(5000)
        print(f"🌍 Public URL (for Colab): {public_url}")
        print("   Use this URL to access your dashboard from anywhere!")
        
    except:
        print("📱 For Google Colab users:")
        print("   The dashboard is running locally. To access it in Colab,")
        print("   you may need to use ngrok or Colab's built-in tunneling.")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped.")

if __name__ == "__main__":
    main()