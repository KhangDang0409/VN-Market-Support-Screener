import json, os, re, time, threading
from pathlib import Path
from flask import Flask, request, send_from_directory
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 65536
ROOT = Path(__file__).parent
lock = threading.Lock()
cache = {}
@app.get('/')
def home(): return send_from_directory(ROOT/'public', 'index.html')
@app.get('/<path:name>')
def static(name): return send_from_directory(ROOT/'public', name)
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.get('/api/source')
def source(): return send_from_directory(ROOT, 'engine.py', mimetype='text/plain')
@app.get('/api/project')
def project():
    url = os.getenv('GITHUB_REPOSITORY_URL','')
    owner, repo = os.getenv('VERCEL_GIT_REPO_OWNER',''), os.getenv('VERCEL_GIT_REPO_SLUG','')
    if not url and owner and repo: url = f'https://github.com/{owner}/{repo}'
    if not re.fullmatch(r'https://github.com/[\w.-]+/[\w.-]+/?',url): url = '/api/source'
    return {'github_url':url}
@app.post('/api/screen')
def screen():
    p = request.get_json(silent=True)
    try:
        if not isinstance(p,dict) or not isinstance(p.get('tickers'),str): raise ValueError('Enter a comma-separated ticker list.')
        tickers = [t.strip().upper() for t in p['tickers'].split(',') if t.strip()]
        threshold = float(p.get('liquidity',20))
        if not tickers or not all(re.fullmatch(r'[A-Z0-9]+(?:\.VN)?',t) for t in tickers): raise ValueError('Enter valid Vietnamese stock symbols.')
        if not 1 <= threshold < float('inf'): raise ValueError('Minimum liquidity must be at least 1 billion VND.')
    except (TypeError,ValueError) as e: return {'error':str(e)},400
    if not lock.acquire(False): return {'error':'Another scan is running. Please try again shortly.'},429
    try:
        # Lazy imports keep project metadata available if a model dependency fails.
        import tempfile
        import engine
        import plotly.graph_objects as go
        engine.yf.set_tz_cache_location(tempfile.gettempdir()+'/vn-screener-yf')
        key=(tuple(tickers),threshold)
        now=time.time()
        for k in list(cache):
            if now-cache[k][0]>=900: del cache[k]
        cached=key in cache
        if cached: stamp,rows=cache[key]
        else:
            rows=engine.process_market_data(tickers,threshold).to_dict('records')
            stamp=time.time()
            if len(cache)>=32: cache.pop(next(iter(cache)))
            cache[key]=(stamp,rows)
        chart=None; chart_error=None
        if rows:
            try:
                df=engine.yf.download(f"{rows[0]['Ticker']}.VN",period='6mo',progress=False)
                if isinstance(df.columns,engine.pd.MultiIndex): df.columns=df.columns.droplevel(1)
                if df.empty: raise ValueError('No chart data returned.')
                fig=go.Figure(data=[go.Candlestick(x=df.index,open=df['Open'],high=df['High'],low=df['Low'],close=df['Close'],name='Price')])
                fig.add_hline(y=rows[0]['Support Level'],line_dash='dash',line_color='rgba(0, 255, 127, 0.8)',annotation_text='Support / Stoploss Level')
                fig.update_layout(template='plotly_dark',height=500,margin=dict(l=0,r=0,t=30,b=0),xaxis_rangeslider_visible=False)
                chart=json.loads(fig.to_json())
            except Exception:
                app.logger.exception('Chart failed')
                chart_error='Screening results are available, but chart data could not be loaded.'
        return {'rows':rows,'chart':chart,'chart_error':chart_error,'cached':cached,'scanned_at':stamp}
    except Exception:
        app.logger.exception('Screen failed')
        return {'error':'The scan failed. Please retry; check Vercel runtime logs if it persists.'},502
    finally: lock.release()
