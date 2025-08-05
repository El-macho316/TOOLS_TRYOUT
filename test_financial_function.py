import json
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from decimal import Decimal

# ========================================
# CONFIGURATION CONSTANTS
# ========================================

# Scoring thresholds for financial metrics
class ScoringThresholds:
    PE_EXCELLENT = 15
    PE_GOOD = 20
    ROE_EXCELLENT = 20
    ROE_GOOD = 10
    EV_EBITDA_EXCELLENT = 10
    EV_EBITDA_GOOD = 15
    EPS_EXCELLENT = 5
    EPS_GOOD = 1

# Scoring weights for different metrics
class ScoringWeights:
    PE_RATIO = 0.25
    ROE = 0.25
    EV_EBITDA = 0.25
    EPS = 0.25

# Score values
class ScoreValues:
    EXCELLENT = 100
    GOOD = 80
    FAIR = 70
    POOR = 50
    VERY_POOR = 40

# Valuation categories
class ValuationCategories:
    UNDERVALUED_THRESHOLD = 80
    FAIRLY_VALUED_THRESHOLD = 60
    
    UNDERVALUED = "Undervalued"
    FAIRLY_VALUED = "Fairly valued"
    OVERVALUED = "Overvalued"

# ========================================
# MOCK DATA
# ========================================

MOCK_FINANCIAL_DATA = {
    "AAPL": {
        "companyName": "Apple Inc.",
        "peRatio": 28.5,
        "roe": 22.4,
        "evToEbitda": 18.2,
        "eps": 6.05,
        "debtToEquity": 0.31,
        "marketCap": 2800000000000,  # 2.8T
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "closePrice": 175.84,
        "totalScore": 85,
        "fundamentalScore": 82,
        "technicalScore": 88,
        "quantScore": 85,
        "rank": 15,
        "tradeDate": "2024-01-15"
    },
    "MSFT": {
        "companyName": "Microsoft Corporation",
        "peRatio": 32.1,
        "roe": 18.7,
        "evToEbitda": 22.4,
        "eps": 9.65,
        "debtToEquity": 0.47,
        "marketCap": 2750000000000,  # 2.75T
        "sector": "Technology",
        "industry": "Software",
        "closePrice": 370.73,
        "totalScore": 78,
        "fundamentalScore": 75,
        "technicalScore": 82,
        "quantScore": 77,
        "rank": 28,
        "tradeDate": "2024-01-15"
    },
    "GOOGL": {
        "companyName": "Alphabet Inc.",
        "peRatio": 24.8,
        "roe": 15.2,
        "evToEbitda": 14.7,
        "eps": 5.80,
        "debtToEquity": 0.12,
        "marketCap": 1650000000000,  # 1.65T
        "sector": "Technology",
        "industry": "Internet Services",
        "closePrice": 139.69,
        "totalScore": 82,
        "fundamentalScore": 80,
        "technicalScore": 85,
        "quantScore": 81,
        "rank": 20,
        "tradeDate": "2024-01-15"
    },
    "TSLA": {
        "companyName": "Tesla Inc.",
        "peRatio": 48.9,
        "roe": 19.3,
        "evToEbitda": 32.1,
        "eps": 4.30,
        "debtToEquity": 0.17,
        "marketCap": 650000000000,  # 650B
        "sector": "Consumer Discretionary",
        "industry": "Electric Vehicles",
        "closePrice": 207.83,
        "totalScore": 65,
        "fundamentalScore": 60,
        "technicalScore": 72,
        "quantScore": 63,
        "rank": 95,
        "tradeDate": "2024-01-15"
    },
    "NVDA": {
        "companyName": "NVIDIA Corporation",
        "peRatio": 64.2,
        "roe": 28.1,
        "evToEbitda": 45.3,
        "eps": 12.28,
        "debtToEquity": 0.24,
        "marketCap": 1750000000000,  # 1.75T
        "sector": "Technology",
        "industry": "Semiconductors",
        "closePrice": 722.48,
        "totalScore": 70,
        "fundamentalScore": 68,
        "technicalScore": 75,
        "quantScore": 67,
        "rank": 75,
        "tradeDate": "2024-01-15"
    },
    "JPM": {
        "companyName": "JPMorgan Chase & Co.",
        "peRatio": 12.8,
        "roe": 16.4,
        "evToEbitda": 8.9,
        "eps": 15.36,
        "debtToEquity": 1.18,
        "marketCap": 485000000000,  # 485B
        "sector": "Financial Services",
        "industry": "Banking",
        "closePrice": 168.12,
        "totalScore": 88,
        "fundamentalScore": 92,
        "technicalScore": 85,
        "quantScore": 87,
        "rank": 8,
        "tradeDate": "2024-01-15"
    },
    "WMT": {
        "companyName": "Walmart Inc.",
        "peRatio": 26.7,
        "roe": 12.8,
        "evToEbitda": 12.4,
        "eps": 2.32,
        "debtToEquity": 0.56,
        "marketCap": 460000000000,  # 460B
        "sector": "Consumer Staples",
        "industry": "Retail",
        "closePrice": 165.89,
        "totalScore": 75,
        "fundamentalScore": 78,
        "technicalScore": 73,
        "quantScore": 74,
        "rank": 45,
        "tradeDate": "2024-01-15"
    }
}

# ========================================
# UTILITY FUNCTIONS
# ========================================

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

def format_market_cap(market_cap: Optional[float]) -> str:
    if market_cap is None:
        return "N/A"
    
    if market_cap >= 1_000_000_000_000:  # Trillions
        return f"${market_cap / 1_000_000_000_000:.2f}T"
    elif market_cap >= 1_000_000_000:  # Billions
        return f"${market_cap / 1_000_000_000:.2f}B"
    elif market_cap >= 1_000_000:  # Millions
        return f"${market_cap / 1_000_000:.2f}M"
    else:
        return f"${market_cap:,.0f}"

def get_performance_indicator(score: int) -> str:
    if score >= 90:
        return "🟢 Excellent"
    elif score >= 80:
        return "🔵 Very Good"
    elif score >= 70:
        return "🟡 Good"
    elif score >= 60:
        return "🟠 Fair"
    elif score >= 50:
        return "🔴 Poor"
    else:
        return "⚫ Very Poor"

def get_valuation_indicator(valuation: str) -> str:
    if valuation == "Undervalued":
        return "💚 Undervalued (Potential Buy)"
    elif valuation == "Fairly valued":
        return "💙 Fairly Valued (Hold/Monitor)"
    else:
        return "❤️ Overvalued (Consider Carefully)"

def get_metric_explanation(metric: str) -> str:
    explanations = {
        "peRatio": "Price-to-Earnings: How much investors pay per dollar of earnings (lower is generally better)",
        "roe": "Return on Equity: How efficiently the company uses shareholder money (higher is better)",
        "evToEbitda": "Enterprise Value to EBITDA: Company valuation relative to earnings (lower is better)",
        "eps": "Earnings Per Share: Company's profit per share (higher is better)"
    }
    return explanations.get(metric, "")

# ========================================
# FINANCIAL SCORING ENGINE
# ========================================

class FinancialMetricsScorer:
    @staticmethod
    def score_pe_ratio(pe_ratio: float) -> int:
        if pe_ratio < ScoringThresholds.PE_EXCELLENT:
            return ScoreValues.EXCELLENT
        elif pe_ratio < ScoringThresholds.PE_GOOD:
            return ScoreValues.GOOD
        else:
            return ScoreValues.POOR
    
    @staticmethod
    def score_roe(roe: float) -> int:
        if roe > ScoringThresholds.ROE_EXCELLENT:
            return ScoreValues.EXCELLENT
        elif roe > ScoringThresholds.ROE_GOOD:
            return ScoreValues.GOOD
        else:
            return ScoreValues.POOR
    
    @staticmethod
    def score_ev_ebitda(ev_ebitda: float) -> int:
        if ev_ebitda < ScoringThresholds.EV_EBITDA_EXCELLENT:
            return ScoreValues.EXCELLENT
        elif ev_ebitda < ScoringThresholds.EV_EBITDA_GOOD:
            return ScoreValues.FAIR
        else:
            return ScoreValues.VERY_POOR
    
    @staticmethod
    def score_eps(eps: float) -> int:
        if eps > ScoringThresholds.EPS_EXCELLENT:
            return ScoreValues.EXCELLENT
        elif eps > ScoringThresholds.EPS_GOOD:
            return ScoreValues.FAIR
        else:
            return ScoreValues.VERY_POOR

# ========================================
# MAIN TEST SERVICE CLASS
# ========================================

class TestFinancialDataService:
    def __init__(self):
        self.logger = setup_logger("TestFinancialDataService")
        self.metrics_scorer = FinancialMetricsScorer()
        self.logger.info("Test Financial Data Service initialized with mock data")

    def analyze_stock(self, ticker: str) -> Dict[str, Any]:
        """
        Analyze a stock using mock data for testing purposes
        """
        try:
            ticker = ticker.upper().strip()
            self.logger.info(f"Starting test financial analysis for ticker: {ticker}")
            
            if not ticker:
                return self._create_error_response("Ticker symbol is required")

            financial_data = self._get_mock_financial_data(ticker)
            if financial_data is None:
                return self._create_error_response(
                    f"Mock data not available for '{ticker}'. "
                    f"Available tickers: {', '.join(MOCK_FINANCIAL_DATA.keys())}"
                )

            # Add timestamp to data
            financial_data["dataRetrievedAt"] = datetime.now().isoformat()

            analysis_results = self._perform_financial_analysis(financial_data)

            complete_results = {
                'success': True,
                'ticker': ticker,
                'timestamp': datetime.now().isoformat(),
                'data_source': 'mock_data',
                'data': {
                    **financial_data,
                    **analysis_results
                }
            }

            self.logger.info(f"Test financial analysis completed successfully for {ticker}")
            return complete_results
            
        except Exception as error:
            self.logger.error(f"Test analysis failed for {ticker}: {str(error)}")
            return self._create_error_response(
                f"Internal error during test analysis: {str(error)}"
            )

    def _get_mock_financial_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve mock financial data for testing
        """
        self.logger.info(f"Retrieving mock financial data for: {ticker}")
        
        if ticker not in MOCK_FINANCIAL_DATA:
            self.logger.warning(f"Mock data not found for ticker: {ticker}")
            return None
        
        return MOCK_FINANCIAL_DATA[ticker].copy()

    def _perform_financial_analysis(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        overall_score, score_breakdown, valid_metrics_count = self._calculate_overall_score(financial_data)
        
        if valid_metrics_count == 0:
            return {
                "score": 0,
                "valuation": "Unable to evaluate",
                "rationale": "Insufficient financial data available for meaningful analysis.",
                "scoreBreakdown": {},
                "metricsAnalyzed": 0,
                "userFriendlyReport": "❌ Unable to generate analysis report due to insufficient data."
            }

        valuation_category = self._determine_valuation_category(overall_score)
        analysis_rationale = self._generate_analysis_rationale(
            financial_data, overall_score, valuation_category, valid_metrics_count
        )
        
        analysis_results = {
            "score": round(overall_score, 2),
            "valuation": valuation_category,
            "rationale": analysis_rationale,
            "scoreBreakdown": score_breakdown,
            "metricsAnalyzed": valid_metrics_count
        }
        
        user_friendly_report = self._create_user_friendly_report(financial_data, analysis_results)
        analysis_results["userFriendlyReport"] = user_friendly_report
        
        return analysis_results

    def _calculate_overall_score(self, data: Dict[str, Any]) -> Tuple[float, Dict[str, int], int]:
        total_weighted_score = 0
        score_breakdown = {}
        valid_metrics_count = 0

        if self._is_valid_metric(data.get("peRatio")):
            pe_score = self.metrics_scorer.score_pe_ratio(data["peRatio"])
            total_weighted_score += pe_score * ScoringWeights.PE_RATIO
            score_breakdown["peRatio"] = pe_score
            valid_metrics_count += 1
        
        if self._is_valid_metric(data.get("roe")):
            roe_score = self.metrics_scorer.score_roe(data["roe"])
            total_weighted_score += roe_score * ScoringWeights.ROE
            score_breakdown["roe"] = roe_score
            valid_metrics_count += 1

        if self._is_valid_metric(data.get("evToEbitda")):
            ev_score = self.metrics_scorer.score_ev_ebitda(data["evToEbitda"])
            total_weighted_score += ev_score * ScoringWeights.EV_EBITDA
            score_breakdown["evToEbitda"] = ev_score
            valid_metrics_count += 1
            
        if self._is_valid_metric(data.get("eps")):
            eps_score = self.metrics_scorer.score_eps(data["eps"])
            total_weighted_score += eps_score * ScoringWeights.EPS
            score_breakdown["eps"] = eps_score
            valid_metrics_count += 1

        return total_weighted_score, score_breakdown, valid_metrics_count

    def _is_valid_metric(self, value: Any) -> bool:
        return value is not None and value > 0

    def _determine_valuation_category(self, score: float) -> str:
        if score >= ValuationCategories.UNDERVALUED_THRESHOLD:
            return ValuationCategories.UNDERVALUED
        elif score >= ValuationCategories.FAIRLY_VALUED_THRESHOLD:
            return ValuationCategories.FAIRLY_VALUED
        else:
            return ValuationCategories.OVERVALUED

    def _generate_analysis_rationale(
        self, 
        data: Dict[str, Any], 
        score: float, 
        valuation: str, 
        metrics_count: int
    ) -> str:
        company_name = data.get('companyName', 'Unknown Company')
        
        pe_display = f"{data.get('peRatio', 0):.2f}" if data.get('peRatio') else 'N/A'
        roe_display = f"{data.get('roe', 0):.2f}%" if data.get('roe') else 'N/A'
        ev_display = f"{data.get('evToEbitda', 0):.2f}" if data.get('evToEbitda') else 'N/A'
        eps_display = f"{data.get('eps', 0):.2f}" if data.get('eps') else 'N/A'
        
        rationale = (
            f"TEST Financial Analysis for {company_name}: "
            f"Overall score of {score:.1f}/100 based on {metrics_count} key metrics. "
            f"Key metrics - P/E Ratio: {pe_display}, ROE: {roe_display}, "
            f"EV/EBITDA: {ev_display}, EPS: ${eps_display}. "
            f"Based on this analysis, the stock appears to be {valuation.lower()}."
        )
        
        return rationale

    def _create_user_friendly_report(self, financial_data: Dict[str, Any], analysis_results: Dict[str, Any]) -> str:
        company_name = financial_data.get('companyName', 'Unknown Company')
        overall_score = analysis_results.get('score', 0)
        valuation = analysis_results.get('valuation', 'Unknown')
        score_breakdown = analysis_results.get('scoreBreakdown', {})
        
        report_lines = [
            f"📊 TEST ANALYSIS: {company_name} ({financial_data.get('sector', 'Unknown')})",
            f"💰 Market Cap: {format_market_cap(financial_data.get('marketCap'))}",
            f"📈 Close Price: ${financial_data.get('closePrice', 0):.2f}",
            f"🏆 Rank: #{financial_data.get('rank', 'N/A')}",
            ""
        ]
        
        report_lines.extend([
            f"🎯 Overall Score: {overall_score:.1f}/100 {get_performance_indicator(int(overall_score))}",
            f"💡 {get_valuation_indicator(valuation)}",
            ""
        ])
        
        report_lines.append("📊 Key Metrics:")
        
        metrics_info = [
            ("peRatio", "P/E Ratio", financial_data.get('peRatio'), "x"),
            ("roe", "ROE", financial_data.get('roe'), "%"),
            ("evToEbitda", "EV/EBITDA", financial_data.get('evToEbitda'), "x"),
            ("eps", "EPS", financial_data.get('eps'), "$")
        ]
        
        for metric_key, metric_name, value, unit in metrics_info:
            if value is not None and metric_key in score_breakdown:
                score = score_breakdown[metric_key]
                if unit == "$":
                    value_str = f"${value:.2f}"
                elif unit == "%":
                    value_str = f"{value:.1f}%"
                else:
                    value_str = f"{value:.1f}{unit}"
                
                report_lines.append(f"  {metric_name}: {value_str} {get_performance_indicator(score)}")
        
        report_lines.append("")
        
        # Additional test data information
        report_lines.extend([
            "📋 Additional Test Data:",
            f"  Fundamental Score: {financial_data.get('fundamentalScore', 'N/A')}",
            f"  Technical Score: {financial_data.get('technicalScore', 'N/A')}",
            f"  Quant Score: {financial_data.get('quantScore', 'N/A')}",
            f"  Total Score: {financial_data.get('totalScore', 'N/A')}",
            ""
        ])
        
        if valuation == "Undervalued":
            report_lines.append("💚 Test Recommendation: Consider for investment")
        elif valuation == "Fairly valued":
            report_lines.append("💙 Test Recommendation: Hold or monitor")
        else:
            report_lines.append("❤️ Test Recommendation: Proceed with caution")
        
        report_lines.extend([
            "",
            "🧪 This is a TEST analysis using mock data",
            "⚠️ For educational and testing purposes only. Not investment advice."
        ])
        
        return "\n".join(report_lines)

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        return {
            'success': False,
            'error': error_message,
            'timestamp': datetime.now().isoformat(),
            'data_source': 'mock_data'
        }

    def get_available_tickers(self) -> List[str]:
        """Return list of available tickers in mock data"""
        return list(MOCK_FINANCIAL_DATA.keys())

    def analyze_all_stocks(self) -> Dict[str, Any]:
        """Analyze all stocks in mock data for comparison"""
        results = {}
        for ticker in self.get_available_tickers():
            results[ticker] = self.analyze_stock(ticker)
        return results

# ========================================
# TEST FUNCTIONS
# ========================================

def test_single_stock(ticker: str = "AAPL"):
    """Test analysis for a single stock"""
    print(f"🧪 Testing Financial Analysis for {ticker}")
    print("=" * 50)
    
    service = TestFinancialDataService()
    result = service.analyze_stock(ticker)
    
    if result['success']:
        print(result['data']['userFriendlyReport'])
        print("\n" + "=" * 50)
        print("📊 Raw Analysis Data:")
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"❌ Error: {result['error']}")
    
    return result

def test_multiple_stocks():
    """Test analysis for multiple stocks"""
    print("🧪 Testing Financial Analysis for Multiple Stocks")
    print("=" * 60)
    
    service = TestFinancialDataService()
    available_tickers = service.get_available_tickers()
    
    print(f"Available test tickers: {', '.join(available_tickers)}")
    print("\n")
    
    results = {}
    for ticker in available_tickers[:3]:  # Test first 3 stocks
        print(f"--- Analysis for {ticker} ---")
        result = service.analyze_stock(ticker)
        results[ticker] = result
        
        if result['success']:
            print(result['data']['userFriendlyReport'])
        else:
            print(f"❌ Error: {result['error']}")
        print("\n")
    
    return results

def compare_stocks():
    """Compare all stocks and show rankings"""
    print("🧪 Stock Comparison Analysis")
    print("=" * 60)
    
    service = TestFinancialDataService()
    results = service.analyze_all_stocks()
    
    # Extract scores for comparison
    stock_scores = []
    for ticker, result in results.items():
        if result['success']:
            score = result['data']['score']
            valuation = result['data']['valuation']
            company_name = result['data']['companyName']
            stock_scores.append({
                'ticker': ticker,
                'company': company_name,
                'score': score,
                'valuation': valuation
            })
    
    # Sort by score (descending)
    stock_scores.sort(key=lambda x: x['score'], reverse=True)
    
    print("📊 Stock Rankings by Analysis Score:")
    print("-" * 60)
    for i, stock in enumerate(stock_scores, 1):
        print(f"{i:2d}. {stock['ticker']:5s} - {stock['company']:25s} | "
              f"Score: {stock['score']:5.1f} | {stock['valuation']}")
    
    return stock_scores

# ========================================
# MAIN EXECUTION
# ========================================

if __name__ == "__main__":
    print("🧪 Financial Analysis Testing Suite")
    print("=" * 60)
    
    # Test 1: Single stock analysis
    print("\n1️⃣ Single Stock Test:")
    test_single_stock("AAPL")
    
    print("\n" + "=" * 60)
    
    # Test 2: Multiple stocks analysis
    print("\n2️⃣ Multiple Stocks Test:")
    test_multiple_stocks()
    
    print("\n" + "=" * 60)
    
    # Test 3: Stock comparison
    print("\n3️⃣ Stock Comparison Test:")
    compare_stocks()
    
    print("\n🎉 All tests completed!")
