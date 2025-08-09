RAW FINANCIAL DATA FOR {symbol.upper()}:
Company: {stock_data.get('name', 'Unknown')}
Current Price: ${stock_data.get('price', 0):.2f}
P/E Ratio: {stock_data.get('pe_ratio', 0):.1f}
ROE: {stock_data.get('roe', 0):.1f}%
Debt/Equity: {stock_data.get('debt_to_equity', 0):.1f}
Profit Margin: {stock_data.get('profit_margin', 0):.1f}%
Revenue Growth: {stock_data.get('revenue_growth', 0):.1f}%
Beta: {stock_data.get('beta', 0):.2f}
Sector: {stock_data.get('sector', 'Unknown')}
Market Cap: {stock_data.get('market_cap', 'Unknown')}
Financial Score: {stock_data.get('score', 0)}/100
Market Rank: #{stock_data.get('rank', 0)}
Dividend Yield: {stock_data.get('dividend_yield', 0):.1f}%
Valuation: {result.get('valuation', 'Unknown')}
Recommendation: {result.get('recommendation', 'Unknown')}
Rationale: {result.get('rationale', 'Unknown')}
"""