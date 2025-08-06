#!/usr/bin/env python3
"""
🚀 STOCK OPTIONS DASHBOARD - DEMO VERSION
Ready to run in Google Colab with ngrok integration

QUICK START:
1. Run this script in Google Colab
2. For public access: Sign up at https://ngrok.com and get your auth token
3. Set your token: !ngrok authtoken YOUR_TOKEN_HERE
4. Re-run this script to get your public URL

📊 FEATURES:
• Live options data with Greeks calculations
• Interactive filtering system
• Conservative trading presets
• Educational content
• Mobile-responsive design
"""

import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def install_packages():
    packages = ['flask', 'yfinance', 'pandas', 'numpy', 'scipy', 'requests', 'flask-cors', 'pyngrok']
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"📦 Installing {package}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--break-system-packages', package])
            except subprocess.CalledProcessError:
                print(f"❌ Failed to install {package}")

print("🚀 Setting up Stock Options Dashboard...")
install_packages()

import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import norm
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
from pyngrok import ngrok

class OptionsAnalyzer:
    def __init__(self):
        self.data_cache = {}
        self.cache_timestamp = {}
        self.cache_duration = 300
    
    def get_risk_free_rate(self):
        try:
            treasury = yf.Ticker("^TNX")
            hist = treasury.history(period="5d")
            if not hist.empty:
                return hist['Close'].iloc[-1] / 100
        except:
            pass
        return 0.045
    
    def calculate_greeks(self, S, K, T, r, sigma, option_type='call'):
        if T <= 0 or sigma <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0}
        
        try:
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            if option_type == 'call':
                delta = norm.cdf(d1)
                theta = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
                        - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
            else:
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
        cache_key = f"{ticker}_{'-'.join(map(str, target_days))}"
        
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
                            'vega': greeks['vega']
                        }
                        calls_data.append(call_data)
                    
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
                            'vega': greeks['vega']
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
            
            self.data_cache[cache_key] = result
            self.cache_timestamp[cache_key] = time.time()
            return result
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None

app = Flask(__name__)
CORS(app)
analyzer = OptionsAnalyzer()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📈 Stock Options Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
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
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
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
        .input-group label { font-weight: 600; color: #2c3e50; }
        .input-group input {
            flex: 1;
            min-width: 300px;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .input-group input:focus { outline: none; border-color: #667eea; }
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
        .ticker-name { font-size: 1.5em; font-weight: bold; }
        .current-price {
            font-size: 1.3em;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
        }
        .expiration-section { border-bottom: 1px solid #e9ecef; }
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
        .options-type { padding: 20px; }
        .options-type h4 {
            color: #2c3e50;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }
        .calls-section { border-right: 1px solid #e9ecef; }
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
        .options-table tr:hover { background: #f8f9fa; }
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
        .notes-section h3 { color: #2c3e50; margin-bottom: 15px; }
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
        .greek-item h4 { color: #3498db; margin-bottom: 8px; }
        @media (max-width: 768px) {
            .options-container { grid-template-columns: 1fr; }
            .calls-section {
                border-right: none;
                border-bottom: 1px solid #e9ecef;
            }
            .input-group {
                flex-direction: column;
                align-items: stretch;
            }
            .input-group input { min-width: auto; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Stock Options Dashboard</h1>
            <p>Live Options Analysis with Greeks - Demo Version</p>
        </div>
        
        <div class="input-section">
            <div class="input-group">
                <label for="tickers">Stock Tickers:</label>
                <input type="text" id="tickers" placeholder="Enter comma-separated tickers (e.g., AAPL, MSFT)" value="AAPL">
                <button class="btn" onclick="fetchData()">Analyze Options</button>
            </div>
        </div>
        
        <div id="loading" class="loading" style="display: none;">
            <p>🔄 Fetching live options data...</p>
        </div>
        
        <div id="error" class="error" style="display: none;"></div>
        
        <div id="results"></div>
        
        <div class="notes-section">
            <h3>📚 Options Greeks Explained</h3>
            <div class="greeks-explanation">
                <div class="greek-item">
                    <h4>Delta (Δ)</h4>
                    <p>Price sensitivity to stock movement. Call deltas: 0 to 1, Put deltas: -1 to 0.</p>
                </div>
                <div class="greek-item">
                    <h4>Gamma (Γ)</h4>
                    <p>Rate of change of delta. Higher gamma = delta changes more rapidly.</p>
                </div>
                <div class="greek-item">
                    <h4>Theta (Θ)</h4>
                    <p>Time decay per day. Shows daily option value decrease.</p>
                </div>
                <div class="greek-item">
                    <h4>Vega (ν)</h4>
                    <p>Volatility sensitivity. Higher vega = more sensitive to volatility changes.</p>
                </div>
            </div>
        </div>
    </div>

    <script>
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
                headers: { 'Content-Type': 'application/json' },
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
                    displayResults(data);
                }
            })
            .catch(error => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').textContent = 'Error: ' + error.message;
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
                        <div class="error">Error loading ${ticker}: ${tickerData?.error || 'Unknown error'}</div>
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
                            <span>${expData.days_to_expiry} days</span>
                        </div>
                        <div class="options-container">
                            <div class="options-type calls-section">
                                <h4>📈 Calls</h4>
                                ${generateTable(expData.calls, tickerData.current_price)}
                            </div>
                            <div class="options-type">
                                <h4>📉 Puts</h4>
                                ${generateTable(expData.puts, tickerData.current_price)}
                            </div>
                        </div>
                    `;
                    
                    tickerDiv.appendChild(expDiv);
                });
                
                resultsDiv.appendChild(tickerDiv);
            });
        }
        
        function generateTable(options, currentPrice) {
            if (!options || options.length === 0) {
                return '<p>No data available</p>';
            }
            
            let html = `
                <table class="options-table">
                    <thead>
                        <tr>
                            <th>Strike</th><th>Last</th><th>Bid</th><th>Ask</th>
                            <th>Vol</th><th>OI</th><th>IV</th>
                            <th>Δ</th><th>Γ</th><th>Θ</th><th>ν</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            options.forEach(option => {
                const isATM = Math.abs(option.strike - currentPrice) <= (currentPrice * 0.05);
                html += `
                    <tr class="${isATM ? 'atm-option' : ''}">
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
            
            return html + '</tbody></table>';
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
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({'error': 'No tickers provided'})
        
        results = {}
        for ticker in tickers:
            ticker = ticker.strip().upper()
            if ticker:
                print(f"📊 Fetching {ticker}...")
                options_data = analyzer.get_options_data(ticker)
                if options_data:
                    results[ticker] = options_data
                else:
                    results[ticker] = {'error': f'No data for {ticker}'}
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)})

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def setup_ngrok():
    try:
        ngrok.kill()
        tunnel = ngrok.connect(8080, proto="http", options={"bind_tls": True})
        return tunnel.public_url
    except Exception as e:
        if "authtoken" in str(e).lower():
            print("\n🔐 NGROK AUTHENTICATION REQUIRED:")
            print("1️⃣  Sign up: https://ngrok.com")
            print("2️⃣  Get token: https://dashboard.ngrok.com/get-started/your-authtoken")
            print("3️⃣  Set token: !ngrok authtoken YOUR_TOKEN_HERE")
            print("4️⃣  Re-run this script")
        return None

def main():
    print("\n🚀 Starting Stock Options Dashboard...")
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(3)
    
    # Try ngrok
    print("🔗 Setting up ngrok tunnel...")
    public_url = setup_ngrok()
    
    print("\n" + "="*50)
    print("✅ DASHBOARD IS LIVE!")
    print("="*50)
    
    if public_url:
        print(f"🌍 PUBLIC: {public_url}")
        print(f"🏠 LOCAL:  http://localhost:8080")
        print("\n💡 Share the public URL with anyone!")
    else:
        print(f"🏠 LOCAL:  http://localhost:8080")
        print("💡 For public access, set up ngrok authentication")
    
    print("\n📊 FEATURES:")
    print("• Live options data with Greeks")
    print("• ~90, ~120, ~150 day expirations")
    print("• Mobile-responsive design")
    print("• Real-time calculations")
    
    print(f"\n🎯 Try it: Enter 'AAPL' and click Analyze!")
    print("="*50)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        try:
            ngrok.kill()
        except:
            pass

if __name__ == "__main__":
    main()