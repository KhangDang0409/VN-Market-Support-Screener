import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import engine
from app import app, cache

def frame(kind='breakout'):
    close=np.linspace(100,130,150)
    volume=np.full(150,1e9)
    if kind=='flat': close[:]=100
    if kind=='illiquid': volume[:]=1
    if kind=='breakout': close[-1]=140;volume[-1]=2e9
    return pd.DataFrame({'Open':close,'High':close+1,'Low':close-1,'Close':close,'Volume':volume},index=pd.date_range('2025-01-01',periods=150))
class Tests(unittest.TestCase):
    def setUp(self): cache.clear()
    def test_breakout(self):
        with patch.object(engine.yf,'download',return_value=frame()):
            rows=engine.process_market_data(['FPT'],20)
        self.assertEqual(rows.iloc[0]['Setup'],'🔥 Confirmed Breakout')
        self.assertEqual(rows.iloc[0]['Support Level'],round(frame()['High'].iloc[-61:-1].max(),2))
        self.assertEqual(rows.iloc[0]['Price'],140)
    def test_filters(self):
        for kind in ['flat','illiquid']:
            with patch.object(engine.yf,'download',return_value=frame(kind)):
                self.assertTrue(engine.process_market_data(['FPT'],20).empty)
    def test_empty_and_short(self):
        for df in [pd.DataFrame(),frame().head(119)]:
            with patch.object(engine.yf,'download',return_value=df):self.assertTrue(engine.process_market_data(['FPT'],20).empty)
    def test_multiindex_and_order(self):
        df=frame();df.columns=pd.MultiIndex.from_product([df.columns,['X']])
        with patch.object(engine.yf,'download',return_value=df):
            rows=engine.process_market_data(['FPT.VN','ACB','FPT'],20)
        self.assertEqual(rows.Ticker.tolist(),['FPT','ACB','FPT'])
    def test_rsi(self):
        s=pd.Series([100.,105.,102.,107.,101.]); d=s.diff()
        expected=100-100/(1+d.clip(lower=0).fillna(0).ewm(alpha=1/14,adjust=False).mean()/(-d.clip(upper=0).fillna(0)).ewm(alpha=1/14,adjust=False).mean())
        pd.testing.assert_series_equal(engine.calculate_rsi(s),expected)
    def test_poc(self):
        df=frame();h,e=np.histogram(df.Close,bins=20,weights=df.Volume)
        self.assertEqual(engine.calculate_volume_profile_poc(df),(e[h.argmax()]+e[h.argmax()+1])/2)
    def test_api_cache_chart(self):
        with patch.object(engine.yf,'download',return_value=frame()) as dl:
            c=app.test_client();p={'tickers':'FPT','liquidity':20}
            first=c.post('/api/screen',json=p);second=c.post('/api/screen',json=p)
            self.assertEqual(first.status_code,200);self.assertFalse(first.json['cached']);self.assertTrue(second.json['cached'])
            self.assertEqual(dl.call_count,3);self.assertEqual(first.json['chart']['data'][0]['type'],'candlestick')
    def test_routes_validation(self):
        c=app.test_client()
        for path in ['/','/client.js','/style.css','/api/source','/api/project','/api/health']:self.assertEqual(c.get(path).status_code,200)
        for p in [{},{'tickers':''},{'tickers':'FPT','liquidity':0}]:self.assertEqual(c.post('/api/screen',json=p).status_code,400)
if __name__=='__main__':unittest.main()
