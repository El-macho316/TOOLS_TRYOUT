import json
import os
import random
from datetime import datetime
from crewai import Agent, Task, Crew
from crewai_tools import tool
from langchain_anthropic import ChatAnthropic
# Load environment variables
from dotenv import load_dotenv
load_dotenv()
from langfuse import get_client

# Initialize Langfuse client using environment variables:
#   LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
# If not configured, SDK will be disabled gracefully.
langfuse = get_client()

# Configure Anthropic Caapolaude directly
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

# Mock Financial Data Service
class MockFinancialDataService:
    def __init__(self):
        self.mock_stocks = {
            'AAPL': {
                'name': 'Apple Inc.',
                'price': 175.43,
                'pe_ratio': 28.5,
                'roe': 147.25,
                'debt_to_equity': 1.2,
                'profit_margin': 25.3,
                'revenue_growth': 8.2,
                'sector': 'Technology',
                'market_cap': '2.8T',
                'dividend_yield': 0.5,
                'beta': 1.29,
                'score': 85,
                'rank': 15
            },
            'MSFT': {
                'name': 'Microsoft Corporation',
                'price': 378.85,
                'pe_ratio': 35.2,
                'roe': 39.1,
                'debt_to_equity': 0.8,
                'profit_margin': 36.8,
                'revenue_growth': 14.5,
                'sector': 'Technology',
                'market_cap': '2.9T',
                'dividend_yield': 0.8,
                'beta': 0.88,
                'score': 92,
                'rank': 8
            },
            'GOOGL': {
                'name': 'Alphabet Inc.',
                'price': 142.56,
                'pe_ratio': 25.8,
                'roe': 25.4,
                'debt_to_equity': 0.3,
                'profit_margin': 23.1,
                'revenue_growth': 12.8,
                'sector': 'Technology',
                'market_cap': '1.8T',
                'dividend_yield': 0.0,
                'beta': 1.05,
                'score': 78,
                'rank': 25
            },
            'TSLA': {
                'name': 'Tesla Inc.',
                'price': 248.42,
                'pe_ratio': 78.9,
                'roe': 23.8,
                'debt_to_equity': 0.4,
                'profit_margin': 8.2,
                'revenue_growth': 19.3,
                'sector': 'Automotive',
                'market_cap': '790B',
                'dividend_yield': 0.0,
                'beta': 2.34,
                'score': 65,
                'rank': 45
            },
            'AMZN': {
                'name': 'Amazon.com Inc.',
                'price': 155.23,
                'pe_ratio': 60.2,
                'roe': 15.8,
                'debt_to_equity': 1.1,
                'profit_margin': 3.8,
                'revenue_growth': 11.2,
                'sector': 'Consumer Discretionary',
                'market_cap': '1.6T',
                'dividend_yield': 0.0,
                'beta': 1.18,
                'score': 72,
                'rank': 32
            }
        }
    
    def analyze_stock(self, symbol):
        """Mock stock analysis"""
        symbol = symbol.upper()
        if symbol in self.mock_stocks:
            stock = self.mock_stocks[symbol]
            
            # Calculate valuation assessment
            if stock['pe_ratio'] < 15:
                valuation = "Undervalued"
            elif stock['pe_ratio'] < 25:
                valuation = "Fairly Valued"
            else:
                valuation = "Overvalued"
            
            # Generate recommendation
            if stock['score'] >= 80:
                recommendation = "BUY"
                rationale = "Strong financial metrics and growth potential"
            elif stock['score'] >= 60:
                recommendation = "HOLD"
                rationale = "Moderate performance with some concerns"
            else:
                recommendation = "SELL"
                rationale = "Weak financial metrics and poor outlook"
            
            # Create user-friendly report
            report = f"""
📊 FUNDAMENTAL ANALYSIS: {symbol} ({stock['name']})
{'='*50}

💰 CURRENT PRICE: ${stock['price']:.2f}
🏢 SECTOR: {stock['sector']}
📈 MARKET CAP: {stock['market_cap']}

📊 KEY METRICS:
• P/E Ratio: {stock['pe_ratio']:.1f}
• ROE: {stock['roe']:.1f}%
• Debt/Equity: {stock['debt_to_equity']:.1f}
• Profit Margin: {stock['profit_margin']:.1f}%
• Revenue Growth: {stock['revenue_growth']:.1f}%
• Beta: {stock['beta']:.2f}

🏆 SCORING:
• Financial Score: {stock['score']}/100
• Market Rank: #{stock['rank']}
• Valuation: {valuation}

💡 RECOMMENDATION: {recommendation}
📝 Rationale: {rationale}

⚠️  RISK FACTORS:
• Market volatility
• Sector-specific risks
• Economic conditions
• Regulatory changes

📋 This analysis is based on mock data for demonstration purposes.
"""
            
            return {
                'success': True,
                'data': stock,
                'userFriendlyReport': report,
                'recommendation': recommendation,
                'valuation': valuation
            }
        else:
            return {
                'success': False,
                'error': f"Stock {symbol} not found in mock database"
            }
    
    def find_similar_stocks(self, symbol, top_k=5):
        """Mock similar stocks finder"""
        symbol = symbol.upper()
        if symbol not in self.mock_stocks:
            return []
        
        target_stock = self.mock_stocks[symbol]
        similar_stocks = []
        
        for sym, stock in self.mock_stocks.items():
            if sym != symbol:
                # Calculate similarity based on sector and metrics
                sector_match = 1.0 if stock['sector'] == target_stock['sector'] else 0.5
                pe_similarity = 1.0 / (1.0 + abs(stock['pe_ratio'] - target_stock['pe_ratio']))
                size_similarity = 1.0 / (1.0 + abs(stock['score'] - target_stock['score']))
                
                similarity_score = (sector_match + pe_similarity + size_similarity) / 3
                
                similar_stocks.append({
                    'security': sym,
                    'similarity_score': similarity_score,
                    'close_price': stock['price'],
                    'total_score': stock['score'],
                    'rank': stock['rank'],
                    'sector': stock['sector']
                })
        
        # Sort by similarity and return top_k
        similar_stocks.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar_stocks[:top_k]

# Initialize mock financial service
financial_service = MockFinancialDataService()
print("✅ Mock Financial Data Service initialized successfully")

# Custom tool to perform fundamental analysis using mock data
@tool("fundamental_analysis")
def fundamental_analysis(symbol: str, analysis_type: str = "comprehensive") -> str:
    """
    Perform fundamental analysis on a stock using mock financial data.
    
    Args:
        symbol: Stock ticker symbol to analyze
        analysis_type: Type of analysis (comprehensive, basic, etc.)
    
    Returns:
        Raw financial data for LLM to analyze
    """
    try:
        result = financial_service.analyze_stock(symbol)
        
        if result.get('success'):
            # Return raw data for LLM to process, not pre-formatted report
            stock_data = result.get('data', {})
            output_data = f"""
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
            return output_data
        else:
            error_msg = f"❌ Error: {result.get('error', 'Unknown error')}"
            return error_msg
                
    except Exception as e:
        error_msg = f"❌ Error calling fundamental analysis: {str(e)}"
        return error_msg

@tool("get_stock_comparison")
def get_stock_comparison(symbol: str, similar_count: int = 5) -> str:
    """
    Get similar stocks for comparison analysis using mock data.
    
    Args:
        symbol: Stock ticker symbol to find comparisons for
        similar_count: Number of similar stocks to return
    
    Returns:
        Raw comparison data for LLM to analyze
    """
    try:
        similar_stocks = financial_service.find_similar_stocks(symbol, similar_count)
        
        if similar_stocks:
            # Return raw data for LLM to process
            comparison_data = f"SIMILAR STOCKS DATA FOR {symbol.upper()}:\n"
            for i, stock in enumerate(similar_stocks, 1):
                comparison_data += f"""
Stock {i}: {stock['security']}
- Similarity Score: {stock['similarity_score']:.3f}
- Price: ${stock['close_price']:.2f}
- Financial Score: {stock['total_score']}/100
- Market Rank: #{stock['rank']}
- Sector: {stock['sector']}
"""
            return comparison_data
        else:
            error_msg = f"❌ No similar stocks found for {symbol}"
            return error_msg
                
    except Exception as e:
        error_msg = f"❌ Error getting stock comparison: {str(e)}"
        return error_msg

# Senior Financial Analyst Agent
financial_analyst = Agent(
    role="Senior Financial Analyst",
    goal="Analyze raw financial data and provide comprehensive fundamental analysis with natural language insights",
    backstory="""You are a seasoned financial analyst with over 15 years of experience in equity research and fundamental analysis. 
    You receive raw financial data and transform it into clear, actionable investment insights. You excel at interpreting 
    financial ratios, explaining valuation metrics, and providing detailed analysis in natural language. You always 
    explain your reasoning and make complex financial concepts accessible to investors.""",
    llm=llm,
    tools=[fundamental_analysis, get_stock_comparison],
    verbose=True,
    allow_delegation=False
)

# Quantitative Research Analyst Agent  
research_analyst = Agent(
    role="Quantitative Research Analyst",
    goal="Analyze peer comparison data and provide supplementary market insights using natural language",
    backstory="""You are a detail-oriented research analyst who excels at analyzing peer comparisons and market positioning. 
    You receive raw comparison data and provide insightful analysis about competitive positioning, sector trends, 
    and relative performance. You excel at explaining market context, competitive advantages, and industry dynamics 
    in clear, natural language that helps investors understand the broader market picture.""",
    llm=llm,
    tools=[fundamental_analysis, get_stock_comparison],
    verbose=True,
    allow_delegation=False
)

# Task for comprehensive fundamental analysis
fundamental_analysis_task = Task(
    description="""
    Perform the PRIMARY fundamental analysis on the requested stock symbol. You will receive raw financial data 
    and must provide a comprehensive analysis in natural language. Your analysis should include:
    
    1. Financial Health Assessment:
       - Use fundamental_analysis tool to get raw financial data
       - Interpret and explain key financial ratios (P/E, ROE, Debt/Equity, Profit Margin)
       - Analyze the overall financial score and market ranking
       - Provide clear valuation assessment with detailed reasoning
    
    2. Investment Recommendation:
       - Clear Buy/Hold/Sell recommendation with detailed justification
       - Explain your reasoning using specific metrics and ratios
       - Discuss key risk factors and considerations
       - Provide actionable insights for investors
    
    IMPORTANT: Use the raw financial data to write a comprehensive, natural language analysis. 
    Explain what each metric means and why it matters for investment decisions.
    DO NOT perform peer comparison - that will be handled by the research analyst.
    """,
    expected_output="A comprehensive fundamental analysis written in natural language with detailed explanations and investment recommendations",
    agent=financial_analyst
)

# Task for peer comparison and supplementary analysis
research_support_task = Task(
    description="""
    Provide SUPPLEMENTARY research to enhance the fundamental analysis by focusing ONLY on:
    
    1. Peer Comparison Analysis:
       - Use get_stock_comparison tool to get raw comparison data
       - Analyze and explain how the target stock compares to peers
       - Identify relative market position and competitive advantages
    
    2. Additional Market Context:
       - Explain sector outlook and positioning
       - Discuss competitive advantages/disadvantages vs peers
       - Provide market timing considerations
    
    IMPORTANT: Use the raw comparison data to write natural language analysis about peer positioning.
    Explain what the similarity scores mean and how they impact investment decisions.
    DO NOT repeat the fundamental analysis already completed by the financial analyst.
    Focus ONLY on peer comparison and market context in natural language.
    """,
    expected_output="Natural language analysis of peer comparisons and market context to complement the main analysis",
    agent=research_analyst
)

# Create the financial analysis crew
crew = Crew(
    agents=[financial_analyst, research_analyst],
    tasks=[fundamental_analysis_task, research_support_task],
    verbose=False,
    process="sequential"
)

def analyze_stock(symbol: str) -> str:
    """
    Main function to analyze a stock using the crew with mock data
    
    Args:
        symbol: Stock ticker symbol to analyze
        
    Returns:
        Comprehensive analysis report
    """
    try:
        # Update task descriptions with the specific symbol
        fundamental_analysis_task.description = f"""
        Perform the PRIMARY fundamental analysis on {symbol.upper()}. You will receive raw financial data 
        and must provide a comprehensive analysis in natural language:
        
        1. Use fundamental_analysis tool with symbol='{symbol.upper()}' to get raw financial data
        2. Analyze and explain each key metric (P/E ratio, ROE, Debt/Equity, Profit Margin, etc.)
        3. Explain what each metric means for {symbol.upper()} and why it matters
        4. Provide detailed valuation assessment with reasoning
        5. Give clear Buy/Hold/Sell recommendation with comprehensive justification
        
        IMPORTANT: Write your analysis in natural language, explaining your reasoning and making 
        complex financial concepts accessible to investors. Use the raw data to tell a story about 
        {symbol.upper()}'s financial health and investment potential.
        
        Focus ONLY on the fundamental analysis. Do NOT do peer comparison.
        """
        
        research_support_task.description = f"""
        Provide SUPPLEMENTARY analysis for {symbol.upper()} using natural language:
        
        1. Use get_stock_comparison tool to get raw comparison data for {symbol.upper()}
        2. Analyze how {symbol.upper()} compares to similar stocks in the market
        3. Explain what the similarity scores mean and their implications
        4. Provide market context and sector positioning analysis
        5. Discuss competitive advantages and industry dynamics
        
        IMPORTANT: Write your analysis in natural language, explaining the peer comparison data 
        and what it means for {symbol.upper()}'s competitive position and investment outlook.
        
        Do NOT repeat the fundamental analysis. Focus only on peer comparison and market context.
        """
        
        # Execute the crew within a Langfuse trace for observability
        with langfuse.start_as_current_span(name="crew3.analyze_stock") as span:
            # Add input context to the trace
            try:
                span.update_trace(input={"symbol": symbol}, tags=["crew3", "financial"], metadata={"module": "crw.crew_3"})
            except Exception:
                # Non-blocking if tracing metadata update fails
                pass

            result = crew.kickoff()

            # Attach result summary to the trace (avoid huge payloads)
            try:
                result_str = str(result)
                truncated_output = result_str if len(result_str) < 8000 else (result_str[:8000] + "... [truncated]")
                span.update_trace(output=truncated_output)
            except Exception:
                pass

        return result
        
    except Exception as e:
        raise e

def extract_stock_symbol(user_input: str) -> str:
    """
    Use LLM to extract stock symbol from natural language input
    """
    try:
        # Create a more specific prompt for the LLM to extract stock symbols
        prompt = f"""
        You are a stock symbol extractor. Extract the stock ticker symbol from this user input.
        
        Available stocks and their mappings:
        - Apple, apple, AAPL -> AAPL
        - Microsoft, microsoft, MSFT -> MSFT  
        - Google, google, GOOGL -> GOOGL
        - Tesla, tesla, TSLA -> TSLA
        - Amazon, amazon, AMZN -> AMZN
        
        User input: "{user_input}"
        
        Instructions:
        1. Look for company names or ticker symbols in the input
        2. Convert company names to their ticker symbols
        3. Return ONLY the ticker symbol (AAPL, MSFT, GOOGL, TSLA, AMZN) or "NONE"
        4. Be flexible with variations like "analysis on apple" should return "AAPL"
        
        Examples:
        - "Tell me about Apple" -> "AAPL"
        - "analysis on apple" -> "AAPL"
        - "What's the analysis for Microsoft?" -> "MSFT"
        - "How is Tesla doing?" -> "TSLA"
        - "Analyze Google stock" -> "GOOGL"
        - "What about Amazon?" -> "AMZN"
        - "Hello there" -> "NONE"
        - "analysis for apple" -> "AAPL"
        - "apple stock analysis" -> "AAPL"
        
        Return only the ticker symbol or NONE:
        """
        
        # Use the LLM to extract the symbol
        response = llm.invoke(prompt)
        extracted_symbol = response.content.strip().upper()
        
        # Validate the extracted symbol
        if extracted_symbol in financial_service.mock_stocks:
            return extracted_symbol
        else:
            print(f"❌ Invalid symbol extracted: '{extracted_symbol}'")
            return None
                
    except Exception as e:
        print(f"❌ Error extracting stock symbol: {str(e)}")
        return None

def chatbot_interface():
    """
    Interactive chatbot interface for stock analysis with natural language processing
    """
    print("🤖 Welcome to the Financial Analysis Chatbot!")
    print("="*50)
    print("Available stocks: AAPL, MSFT, GOOGL, TSLA, AMZN")
    print("Commands: 'quit', 'help', 'stocks'")
    print("="*50)
    print("💡 You can ask in natural language like:")
    print("   • 'Tell me about Apple'")
    print("   • 'What's the analysis for Microsoft?'")
    print("   • 'How is Tesla doing?'")
    print("   • 'Analyze Google stock'")
    print("="*50)
    
    conversation_history = []
    
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("👋 Thanks for using the Financial Analysis Chatbot!")
                break
                
            elif user_input.lower() == 'help':
                print("\n📚 HELP MENU:")
                print("• Ask about stocks in natural language (e.g., 'Tell me about Apple')")
                print("• Type 'stocks' to see available stocks")
                print("• Type 'quit' to exit")
                print("• Type 'help' for this menu")
                continue
                
            elif user_input.lower() == 'stocks':
                print("\n📊 AVAILABLE STOCKS:")
                for symbol, data in financial_service.mock_stocks.items():
                    print(f"• {symbol}: {data['name']} - ${data['price']:.2f}")
                continue
            
            elif not user_input:
                print("❌ Please enter a question or command.")
                continue
            
            # Use LLM to extract stock symbol from natural language
            print(f"\n🔍 Processing your request...")
            symbol = extract_stock_symbol(user_input)
            
            # Fallback: Try direct symbol matching if LLM fails
            if symbol is None:
                # Check if user input contains any stock symbols directly
                user_input_upper = user_input.upper()
                for stock_symbol in financial_service.mock_stocks.keys():
                    if stock_symbol in user_input_upper:
                        symbol = stock_symbol
                        print(f"🔍 Found direct symbol match: {symbol}")
                        break
                
                # Check for company name variations
                if symbol is None:
                    company_mappings = {
                        'apple': 'AAPL',
                        'microsoft': 'MSFT', 
                        'google': 'GOOGL',
                        'tesla': 'TSLA',
                        'amazon': 'AMZN'
                    }
                    
                    user_input_lower = user_input.lower()
                    for company, ticker in company_mappings.items():
                        if company in user_input_lower:
                            symbol = ticker
                            print(f"🔍 Found company name match: {company} -> {symbol}")
                            break
            
            if symbol is None:
                print(f"❌ I couldn't identify a valid stock in your request.")
                print("Available stocks: AAPL, MSFT, GOOGL, TSLA, AMZN")
                print("Try asking like: 'Tell me about Apple' or 'What's the analysis for Microsoft?'")
                continue
            
            # Add to conversation history
            conversation_history.append(f"User asked: '{user_input}' -> Extracted: {symbol}")
            
            print(f"📊 Analyzing {symbol} ({financial_service.mock_stocks[symbol]['name']})... Please wait...")
            
            # Perform analysis using the crew
            result = analyze_stock(symbol)
            
            print("\n" + "="*60)
            print("📊 ANALYSIS COMPLETE")
            print("="*60)
            print(result)
            print("="*60)
            
            # Add response to history
            conversation_history.append(f"Analysis completed for {symbol}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Thanks for using the Financial Analysis Chatbot!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("Please try again or type 'help' for assistance.")

if __name__ == "__main__":
    print("🚀 Financial Analysis Chatbot initialized successfully!")
    print("📊 Using mock data for demonstration...")
    print("🤖 Starting interactive chatbot...")
    print()
    
    try:
        chatbot_interface()
    except Exception as e:
        print(f"❌ Error during chatbot execution: {str(e)}")
        print("\n🔧 To test analysis directly:")
        print("python -c \"from crew_3 import analyze_stock; print(analyze_stock('AAPL'))\"")
    finally:
        # Ensure traces are flushed when the process terminates
        try:
            langfuse.flush()
        except Exception:
            pass
