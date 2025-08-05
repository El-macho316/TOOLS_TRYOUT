import json
import os
import re
import boto3
from crewai import Agent, Task, Crew
from crewai_tools import tool
from langchain_anthropic import ChatAnthropic

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

# Initialize AWS Lambda client
try:
    lambda_client = boto3.client('lambda')
    print("✅ AWS Lambda client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize AWS Lambda client: {str(e)}")
    print("Make sure AWS credentials are configured properly")
    exit(1)

# Configure Lambda function name
LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "financial-data-service")

def invoke_lambda_function(function_name: str, payload: dict) -> dict:
    """
    Invoke AWS Lambda function with given payload
    
    Args:
        function_name: Name of the Lambda function to invoke
        payload: JSON payload to send to the function
        
    Returns:
        Lambda function response
    """
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Parse the response
        response_payload = json.loads(response['Payload'].read())
        
        # Handle Lambda errors
        if response.get('FunctionError'):
            return {
                'success': False,
                'error': f"Lambda function error: {response_payload}"
            }
            
        return response_payload
        
    except Exception as e:
        return {
            'success': False,
            'error': f"Error invoking Lambda function: {str(e)}"
        }

# Custom tool to perform fundamental analysis using AWS Lambda
@tool("fundamental_analysis")
def fundamental_analysis(symbol: str, analysis_type: str = "comprehensive") -> str:
    """
    Perform fundamental analysis on a stock using AWS Lambda financial data service.
    
    Args:
        symbol: Stock ticker symbol to analyze
        analysis_type: Type of analysis (comprehensive, basic, etc.)
    
    Returns:
        Fundamental analysis results as a formatted string
    """
    try:
        # Prepare payload for Lambda function
        payload = {
            'action': 'analyze_stock',
            'symbol': symbol.upper(),
            'analysis_type': analysis_type
        }
        
        # Call AWS Lambda function
        result = invoke_lambda_function(LAMBDA_FUNCTION_NAME, payload)
        
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
        return f"❌ Error calling AWS Lambda fundamental analysis: {str(e)}"

@tool("get_stock_comparison")
def get_stock_comparison(symbol: str, similar_count: int = 5) -> str:
    """
    Get similar stocks for comparison analysis using AWS Lambda financial data service.
    
    Args:
        symbol: Stock ticker symbol to find comparisons for
        similar_count: Number of similar stocks to return
    
    Returns:
        Similar stocks data as formatted string
    """
    try:
        # Prepare payload for Lambda function
        payload = {
            'action': 'find_similar_stocks',
            'symbol': symbol.upper(),
            'top_k': similar_count
        }
        
        # Call AWS Lambda function
        result = invoke_lambda_function(LAMBDA_FUNCTION_NAME, payload)
        
        if result.get('success'):
            similar_stocks = result.get('data', [])
            
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
            return f"❌ Error getting stock comparison: {result.get('error', 'Unknown error')}"
            
    except Exception as e:
        return f"❌ Error getting stock comparison from AWS Lambda: {str(e)}"

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
    Main function to analyze a stock using the crew with AWS Lambda data services
    
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

def print_welcome():
    """Print welcome message and instructions"""
    print("\n" + "="*70)
    print("🤖 FINANCIAL ANALYSIS CHATBOT")
    print("="*70)
    print("👋 Hi! I'm your AI Financial Analyst assistant!")
    print("💼 I can help you analyze stocks and make investment decisions.")
    print("\n💬 Just talk to me naturally! Here are some examples:")
    print("   • 'Analyze Apple stock'")
    print("   • 'What do you think about Tesla?'")
    print("   • 'Should I invest in Microsoft?'")
    print("   • 'Compare Amazon with its competitors'")
    print("   • 'AAPL' (just the ticker symbol works too!)")
    print("\n🔧 Commands: 'help' for more info, 'quit' to exit")
    print("="*70)

def print_help():
    """Print help information"""
    print("\n📚 HOW TO CHAT WITH ME:")
    print("-" * 60)
    print("🗣️  Natural Language Examples:")
    print("   • 'Analyze Apple stock' or 'Tell me about AAPL'")
    print("   • 'What's your opinion on Tesla?'")
    print("   • 'Should I buy Microsoft shares?'")
    print("   • 'Compare Google with its competitors'")
    print("   • 'Give me analysis of KBANK'")
    print("   • Just type 'AAPL' or any ticker symbol")
    print("\n📊 What I'll provide:")
    print("   • Comprehensive fundamental analysis")
    print("   • Investment recommendations (Buy/Hold/Sell)")
    print("   • Peer comparisons and market context")
    print("   • Risk assessment and key insights")
    print("\n🔧 Commands:")
    print("   • 'help' - Show this help")
    print("   • 'quit', 'exit', 'bye' - Exit our conversation")
    print("\n💡 Tips:")
    print("   • I understand both company names and ticker symbols")
    print("   • Ask follow-up questions about any analysis")
    print("   • Request specific aspects like 'P/E ratio of Apple'")
    print("-" * 60)

def extract_stock_symbol(user_input):
    """
    Extract stock symbol from natural language input
    
    Args:
        user_input: User's natural language input
        
    Returns:
        tuple: (symbol, confidence) where symbol is the extracted ticker and confidence is how sure we are
    """
    # Common company name to ticker mappings
    company_mappings = {
        'apple': 'AAPL',
        'microsoft': 'MSFT', 
        'google': 'GOOGL',
        'alphabet': 'GOOGL',
        'amazon': 'AMZN',
        'tesla': 'TSLA',
        'facebook': 'META',
        'meta': 'META',
        'netflix': 'NFLX',
        'nvidia': 'NVDA',
        'samsung': 'SSNLF',
        'toyota': 'TM',
        'kasikorn': 'KBANK',
        'kasikornbank': 'KBANK',
        'kbank': 'KBANK',
        'ptt': 'PTT',
        'true': 'TRUE',
        'cp': 'CP',
        'cpall': 'CPALL'
    }
    
    # Clean input
    cleaned_input = user_input.lower().strip()
    
    # Method 1: Look for explicit ticker symbols (2-5 uppercase letters)
    ticker_pattern = r'\b[A-Z]{2,5}\b'
    tickers = re.findall(ticker_pattern, user_input.upper())
    if tickers:
        return tickers[0], 'high'
    
    # Method 2: Look for company names in our mapping
    for company, ticker in company_mappings.items():
        if company in cleaned_input:
            return ticker, 'high'
    
    # Method 3: Look for potential ticker-like patterns in lowercase
    potential_tickers = re.findall(r'\b[a-zA-Z]{2,5}\b', cleaned_input)
    for potential in potential_tickers:
        if potential.upper() in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA', 'KBANK', 'PTT']:
            return potential.upper(), 'medium'
    
    return None, 'none'

def generate_conversational_response(user_input, symbol):
    """Generate a conversational response before analysis"""
    responses = [
        f"Great! Let me analyze {symbol} for you. 📊",
        f"Sure thing! I'll dive deep into {symbol}'s financials. 🔍",
        f"Absolutely! Let me pull up the latest data on {symbol}. 📈",
        f"Perfect choice! Analyzing {symbol} now... 💼",
        f"On it! Getting comprehensive analysis for {symbol}. ⚡"
    ]
    
    # More specific responses based on input content
    if any(word in user_input.lower() for word in ['buy', 'invest', 'purchase']):
        return f"Interesting! You're thinking about investing in {symbol}. Let me analyze if it's a good buy right now. 💰"
    elif any(word in user_input.lower() for word in ['opinion', 'think', 'recommend']):
        return f"You want my professional opinion on {symbol}? Let me crunch the numbers and give you my honest assessment. 🤔"
    elif any(word in user_input.lower() for word in ['compare', 'vs', 'versus']):
        return f"Great idea! I'll analyze {symbol} and compare it with its competitors. 📊"
    
    import random
    return random.choice(responses)

def interactive_chatbot():
    """Main interactive chatbot loop"""
    print_welcome()
    
    while True:
        try:
            # Get user input with a more conversational prompt
            user_input = input("\n💬 What would you like me to analyze? ").strip()
            
            # Handle empty input
            if not user_input:
                print("🤔 I didn't catch that. Try asking me something like 'analyze Apple stock' or just type 'AAPL'!")
                continue
            
            # Handle exit commands
            if any(exit_word in user_input.lower() for exit_word in ['quit', 'exit', 'bye', 'goodbye']):
                print("\n👋 It was great chatting with you!")
                print("💼 Happy investing, and remember - do your own research too! 📈")
                break
            
            # Handle help command
            elif any(help_word in user_input.lower() for help_word in ['help', 'how', 'what can you do']):
                print_help()
                continue
            
            # Try to extract stock symbol from natural language
            symbol, confidence = extract_stock_symbol(user_input)
            
            if symbol and confidence in ['high', 'medium']:
                # Generate conversational response
                response = generate_conversational_response(user_input, symbol)
                print(f"\n{response}")
                print("⏳ This might take a moment while I crunch the numbers...")
                print("-" * 50)
                
                try:
                    # Perform the analysis
                    result = analyze_stock(symbol)
                    
                    print("\n" + "="*60)
                    print(f"🎯 ANALYSIS COMPLETE FOR {symbol}")
                    print("="*60)
                    print(result)
                    
                    # Add a conversational follow-up
                    print(f"\n💡 That's my analysis of {symbol}! Got any questions about the results?")
                    print("   You can ask me about another stock or type 'help' for more options.")
                    
                except Exception as e:
                    print(f"\n❌ Oops! I ran into an issue analyzing {symbol}: {str(e)}")
                    print("\n🛠️  This might help:")
                    print("   • Double-check the stock symbol is correct")
                    print("   • Make sure AWS Lambda functions are set up")
                    print("   • Verify AWS credentials are configured")
                    print(f"\n🔄 Want to try a different stock or need help? Just ask!")
            
            else:
                # Couldn't extract a clear stock symbol
                print("\n🤔 I'm not sure which stock you're asking about.")
                print("💡 Try being more specific, like:")
                print("   • 'Analyze Apple stock'")
                print("   • 'What do you think about TSLA?'")
                print("   • 'Should I invest in Microsoft?'")
                print("   • Or just type the ticker symbol like 'AAPL'")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Thanks for chatting with me!")
            print("💼 Happy investing! 📈")
            break
        except Exception as e:
            print(f"\n❌ Oops! Something unexpected happened: {str(e)}")
            print("💡 No worries! Just try asking again or type 'help' if you need guidance.")

if __name__ == "__main__":
    interactive_chatbot()
