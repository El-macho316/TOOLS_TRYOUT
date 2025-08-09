import json
import os
from crewai import Agent, Task, Crew
from crewai_tools import tool
from langchain_anthropic import ChatAnthropic

# Import local lambda function directly
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lambda_function import FinancialDataService

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure Anthropic Claude directly
# Set your Anthropic API key: $env:ANTHROPIC_API_KEY = "sk-ant-api03-your-key-here"

# Create Anthropic LLM instance
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if anthropic_key:
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_key,
        temperature=0.1
    )
    print("✅ Using Anthropic Claude 3 Haiku")
else:
    print("⚠️  ANTHROPIC_API_KEY not found. Please set it first.")
    print("   Use: $env:ANTHROPIC_API_KEY = 'sk-ant-api03-your-key-here'")
    exit(1)

# Initialize local financial data service
try:
    financial_service = FinancialDataService()
    print("✅ Local Financial Data Service initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Financial Data Service: {str(e)}")
    print("Make sure PINECONE_API_KEY is set in your environment variables")
    exit(1)

# Custom tool to perform fundamental analysis using local lambda function
@tool("fundamental_analysis")
def fundamental_analysis(symbol: str, analysis_type: str = "comprehensive") -> str:
    """
    Perform fundamental analysis on a stock using local financial data service.
    
    Args:
        symbol: Stock ticker symbol to analyze
        analysis_type: Type of analysis (comprehensive, basic, etc.)
    
    Returns:
        Fundamental analysis results as a formatted string
    """
    try:
        # Call local financial service directly
        result = financial_service.analyze_stock(symbol)
        
        if result.get('success'):
            # Return the user-friendly report if available
            data = result.get('data', {})
            if 'userFriendlyReport' in data:
                return f"📊 FUNDAMENTAL ANALYSIS REPORT\n{'='*50}\n\n{data['userFriendlyReport']}\n\n📋 Technical Details:\n{json.dumps(data, indent=2, default=str)}"
            else:
                return f"Fundamental Analysis Results for {symbol}:\n{json.dumps(data, indent=2, default=str)}"
        else:
            return f"❌ Error performing analysis for {symbol}: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        return f"❌ Error calling local fundamental analysis: {str(e)}"

@tool("get_stock_comparison")
def get_stock_comparison(symbol: str, similar_count: int = 5) -> str:
    """
    Get similar stocks for comparison analysis using local financial data service.
    
    Args:
        symbol: Stock ticker symbol to find comparisons for
        similar_count: Number of similar stocks to return
    
    Returns:
        Similar stocks data as formatted string
    """
    try:
        # Access the stock database from the financial service
        if hasattr(financial_service, 'stock_db'):
            similar_stocks = financial_service.stock_db.find_similar_stocks(
                symbol.upper(), top_k=similar_count
            )
            
            if similar_stocks:
                comparison_report = f"🔍 SIMILAR STOCKS TO {symbol.upper()}\n{'='*40}\n\n"
                for i, stock in enumerate(similar_stocks, 1):
                    comparison_report += f"{i}. {stock['security']} (Similarity: {stock['similarity_score']:.3f})\n"
                    comparison_report += f"   💰 Price: ${stock['close_price']:.2f}\n"
                    comparison_report += f"   📊 Score: {stock['total_score']}/100\n"
                    comparison_report += f"   🏆 Rank: #{stock['rank']}\n"
                    comparison_report += f"   🏢 Sector: {stock['sector']}\n\n"
                
                return comparison_report
            else:
                return f"❌ No similar stocks found for {symbol}"
        else:
            return "❌ Stock database not available for comparison"
            
    except Exception as e:
        return f"❌ Error getting stock comparison: {str(e)}"

# Senior Financial Analyst Agent
financial_analyst = Agent(
    role="Senior Financial Analyst",
    goal="Provide comprehensive fundamental analysis of stocks using advanced financial metrics and local data analysis capabilities",
    backstory="""You are a seasoned financial analyst with over 15 years of experience in equity research and fundamental analysis. 
    You specialize in analyzing company financials, market trends, and investment opportunities. You use local financial 
    data services to fetch comprehensive stock data, then apply your expertise to interpret the metrics and provide 
    actionable investment insights. You excel at explaining complex financial concepts in clear, accessible language.""",
    llm=llm,
    tools=[fundamental_analysis, get_stock_comparison],
    verbose=True,
    allow_delegation=False
)

# Quantitative Research Analyst Agent  
research_analyst = Agent(
    role="Quantitative Research Analyst",
    goal="Support fundamental analysis with detailed financial ratio analysis, peer comparisons, and risk assessment using local data services",
    backstory="""You are a detail-oriented research analyst who excels at diving deep into financial statements, 
    calculating complex financial ratios, and identifying trends that others might miss. You work closely with 
    senior analysts to provide the quantitative backbone for investment decisions. You are skilled at finding 
    comparable companies and performing relative valuation analysis to support investment recommendations.""",
    llm=llm,
    tools=[fundamental_analysis, get_stock_comparison],
    verbose=True,
    allow_delegation=False
)

# Task for comprehensive fundamental analysis
fundamental_analysis_task = Task(
    description="""
    Perform the PRIMARY fundamental analysis on the requested stock symbol. Your analysis should include:
    
    1. Financial Health Assessment:
       - Use fundamental_analysis tool to get key financial ratios (P/E, ROE, EV/EBITDA, EPS)
       - Interpret the overall financial score and market ranking
       - Provide clear valuation assessment (undervalued/fairly valued/overvalued)
    
    2. Investment Recommendation:
       - Clear Buy/Hold/Sell recommendation based on the analysis
       - Supporting rationale with specific metric explanations
       - Key risk factors and considerations
    
    Use the fundamental_analysis tool to gather data and provide a complete standalone analysis report.
    DO NOT perform peer comparison - that will be handled by the research analyst.
    """,
    expected_output="A complete fundamental analysis report with investment recommendation, but WITHOUT peer comparison analysis",
    agent=financial_analyst
)

# Task for peer comparison and supplementary analysis
research_support_task = Task(
    description="""
    Provide SUPPLEMENTARY research to enhance the fundamental analysis by focusing ONLY on:
    
    1. Peer Comparison Analysis:
       - Use get_stock_comparison tool to find similar stocks
       - Compare key metrics with industry peers
       - Identify relative market position
    
    2. Additional Market Context:
       - Sector outlook and positioning
       - Competitive advantages/disadvantages vs peers
       - Market timing considerations
    
    DO NOT repeat the fundamental analysis already completed by the financial analyst.
    Focus ONLY on peer comparison and supplementary market insights.
    """,
    expected_output="Supplementary peer comparison analysis and market context to complement the main analysis",
    agent=research_analyst
)

# Create the financial analysis crew
crew = Crew(
    agents=[financial_analyst, research_analyst],
    tasks=[fundamental_analysis_task, research_support_task],
    verbose=False,  # Reduced verbosity to minimize duplicate output
    process="sequential"  # Tasks will be executed in order
)

def analyze_stock(symbol: str) -> str:
    """
    Main function to analyze a stock using the crew with local data services
    
    Args:
        symbol: Stock ticker symbol to analyze
        
    Returns:
        Comprehensive analysis report
    """
    # Update task descriptions with the specific symbol
    fundamental_analysis_task.description = f"""
    Perform the PRIMARY fundamental analysis on {symbol.upper()}:
    
    1. Use fundamental_analysis tool with symbol='{symbol.upper()}' to get financial data
    2. Interpret key metrics: P/E ratio, ROE, EV/EBITDA, EPS, and overall score
    3. Determine valuation: undervalued/fairly valued/overvalued
    4. Provide clear Buy/Hold/Sell recommendation with rationale
    
    Focus ONLY on the fundamental analysis. Do NOT do peer comparison.
    """
    
    research_support_task.description = f"""
    Provide SUPPLEMENTARY analysis for {symbol.upper()}:
    
    1. Use get_stock_comparison tool to find similar stocks to {symbol.upper()}
    2. Compare {symbol.upper()} metrics with peer group if available
    3. Add market context and sector outlook
    
    Do NOT repeat the fundamental analysis. Focus only on peer comparison and market context.
    """
    
    # Execute the crew
    result = crew.kickoff()
    return result

if __name__ == "__main__":
    print("🚀 Local Financial Analysis Crew initialized successfully!")
    print("📊 Using local lambda function for data analysis...")
    print("Starting PTT analysis...\n")
    
    try:
        # Test the crew with PTT analysis
        result = analyze_stock('KBANK')
        print("\n" + "="*60)
        print("🎯 ANALYSIS COMPLETE")
        print("="*60)
        print(result)
        
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        print("\n🔧 To test local function directly:")
        print("python -c \"from crew import fundamental_analysis; print(fundamental_analysis('PTT', 'comprehensive'))\"")
    
    print(f"\n✨ You can also use analyze_stock('SYMBOL') to analyze other stocks.")
