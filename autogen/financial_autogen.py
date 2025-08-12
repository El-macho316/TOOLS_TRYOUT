import os
import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import autogen
from autogen import ConversableAgent, UserProxyAgent
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LambdaLLMAdapter:
    """Adapter that ALWAYS returns mock data for financial analysis (no Lambda calls)."""
    
    def __init__(self, lambda_function_name: str = None, anthropic_api_key: str = None, use_mock_data: Optional[bool] = None):
        """
        Initialize adapter. This build is locked to mock mode for 100% local execution.
        
        Args:
            lambda_function_name: Not used for local execution (kept for compatibility)
            anthropic_api_key: Anthropic API key for Claude
            use_mock_data: Ignored; mock mode is always enabled
        """
        self.lambda_function_name = lambda_function_name or "local_financial_analysis"
        
        # Force mock mode unconditionally
        self.use_mock_data = True
        
        # Initialize Anthropic client for direct Claude access
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.anthropic_api_key:
            self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)
        else:
            logger.warning("Anthropic API key not provided. Direct Claude access unavailable.")
            self.anthropic_client = None
    
    def invoke_lambda_function(self, ticker: str) -> Dict[str, Any]:
        """
        Return mock financial analysis data (Lambda disabled in this build)
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Analysis results from mock generator matching Lambda schema
        """
        try:
            mock = self._generate_mock_response(ticker)
            logger.info(f"Mock data returned successfully for ticker: {ticker}")
            return mock
        except Exception as e:
            logger.error(f"Error generating mock response: {str(e)}")
            return {"error": str(e)}

    def _generate_mock_response(self, ticker: str) -> Dict[str, Any]:
        """Generate a mock response matching the lambda response schema."""
        from datetime import datetime
        ticker_upper = (ticker or "MOCK").upper()
        # Simple deterministic mock metrics
        base_scores = {
            "peRatio": 18.7,
            "roe": 16.3,
            "evToEbitda": 11.9,
            "eps": 5.4,
            "marketCap": 250_000_000_000,
            "sector": "Technology",
            "industry": "Software",
        }
        score = 82.5
        valuation = "Fairly valued"
        report_lines = [
            f"📊 {ticker_upper} ({base_scores['sector']})",
            f"💰 Market Cap: $250.00B",
            "",
            f"🎯 Overall Score: {score:.1f}/100 🔵 Very Good",
            f"💡 💙 Fairly Valued (Hold/Monitor)",
            "",
            "📊 Key Metrics:",
            f"  P/E Ratio: {base_scores['peRatio']:.1f}x 🔵 Very Good",
            f"  ROE: {base_scores['roe']:.1f}% 🔵 Very Good",
            f"  EV/EBITDA: {base_scores['evToEbitda']:.1f}x 🟡 Good",
            f"  EPS: ${base_scores['eps']:.2f} 🟡 Good",
            "",
            "💙 Recommendation: Hold or monitor",
            "",
            "⚠️ For informational purposes only. Not investment advice.",
        ]
        analysis_report = "\n".join(report_lines)
        technical_data = {
            "success": True,
            "ticker": ticker_upper,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "companyName": ticker_upper,
                **base_scores,
                "score": score,
                "valuation": valuation,
                "scoreBreakdown": {
                    "peRatio": 80,
                    "roe": 80,
                    "evToEbitda": 70,
                    "eps": 70,
                },
                "metricsAnalyzed": 4,
                "userFriendlyReport": analysis_report,
            },
        }
        body = json.dumps({
            "analysisReport": analysis_report,
            "technicalData": technical_data,
        })
        return {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": "FinancialAnalysisActionGroup",
                "function": "getFinancialAnalysis",
                "functionResponse": {
                    "responseBody": {
                        "TEXT": {"body": body}
                    }
                }
            }
        }
    
    def get_claude_response(self, messages: List[Dict[str, str]], model: str = "claude-3-5-sonnet-20241022") -> str:
        """
        Get response from Claude directly
        
        Args:
            messages: List of message dictionaries
            model: Claude model to use
            
        Returns:
            Claude's response
        """
        if not self.anthropic_client:
            return "Anthropic client not initialized. Please provide API key."
        
        try:
            # Format messages for Anthropic API
            formatted_messages = []
            for msg in messages:
                if msg.get("role") == "user":
                    formatted_messages.append({
                        "role": "user",
                        "content": msg.get("content", "")
                    })
                elif msg.get("role") == "assistant":
                    formatted_messages.append({
                        "role": "assistant", 
                        "content": msg.get("content", "")
                    })
            
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=4000,
                messages=formatted_messages
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error getting Claude response: {str(e)}")
            return f"Error: {str(e)}"

class FinancialAnalysisAutoGenSystem:
    """AutoGen system for financial analysis using MOCK data and Claude (no Lambda)."""
    
    def __init__(self, lambda_function_name: str = None, anthropic_api_key: str = None, use_mock_data: Optional[bool] = None):
        """
        Initialize the AutoGen financial analysis system
        
        Args:
            lambda_function_name: Optional - not used for local execution (kept for compatibility)
            anthropic_api_key: Anthropic API key
        """
        self.lambda_adapter = LambdaLLMAdapter(lambda_function_name, anthropic_api_key, use_mock_data)
        self.setup_agents()
    
    def setup_agents(self):
        """Set up AutoGen agents for financial analysis"""
        
        # Configuration for Claude via Anthropic
        claude_config = {
            "model": "claude-3-5-sonnet-20241022",
            "api_key": self.lambda_adapter.anthropic_api_key,
            "api_type": "anthropic"
        }
        
        # Financial Analyst Agent
        self.financial_analyst = ConversableAgent(
            name="financial_analyst",
            system_message="""You are a senior financial analyst specializing in fundamental analysis. 
            Your role is to:
            1. Analyze stock ticker requests
            2. Coordinate with the data_researcher to get financial data
            3. Provide comprehensive investment recommendations
            4. Explain complex financial metrics in simple terms
            5. Consider both quantitative data and qualitative factors
            
            Always provide balanced, well-reasoned analysis and clearly state that your analysis 
            is for informational purposes only and not investment advice.""",
            llm_config={"config_list": [claude_config]},
            human_input_mode="NEVER",
        )
        
        # Data Researcher Agent
        self.data_researcher = ConversableAgent(
            name="data_researcher", 
            system_message="""You are a financial data researcher responsible for gathering comprehensive 
            stock analysis data. Your role is to:
            1. Extract ticker symbols from user requests
            2. Retrieve financial data using the LOCAL financial analysis function
            3. Format and present data clearly
            4. Identify data quality issues or missing information
            5. Provide context about the data sources and methodology
            
            You have access to a sophisticated LOCAL financial analysis system that provides 
            fundamental analysis scores, valuation metrics, and comprehensive reports using Pinecone vector database.""",
            llm_config={"config_list": [claude_config]},
            human_input_mode="NEVER",
        )
        
        # User Proxy Agent
        self.user_proxy = UserProxyAgent(
            name="user_proxy",
            system_message="You are the user's representative in this financial analysis conversation.",
            human_input_mode="ALWAYS",
            max_consecutive_auto_reply=10,
            code_execution_config=False,
        )
        
        # Create wrapper function for registration (AutoGen needs function, not method)
        def get_financial_analysis_func(ticker: str) -> str:
            return self.get_financial_analysis_wrapper(ticker)
        
        # Register function for data researcher to call local Lambda function
        self.data_researcher.register_for_llm(
            name="get_financial_analysis",
            description="Get comprehensive financial analysis for a stock ticker using LOCAL financial analysis function"
        )(get_financial_analysis_func)
        
        self.user_proxy.register_for_execution(
            name="get_financial_analysis"
        )(get_financial_analysis_func)
    
    def get_financial_analysis_wrapper(self, ticker: str) -> str:
        """
        Wrapper function for LOCAL Lambda financial analysis
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Formatted analysis results from local function
        """
        try:
            result = self.lambda_adapter.invoke_lambda_function(ticker)
            
            if "error" in result:
                return f"Error retrieving analysis for {ticker}: {result['error']}"
            
            # Extract and format the response
            response_data = result.get("response", {})
            function_response = response_data.get("functionResponse", {})
            response_body = function_response.get("responseBody", {})
            text_data = response_body.get("TEXT", {})
            body_content = text_data.get("body", "{}")
            
            # Parse the analysis data
            analysis_data = json.loads(body_content) if isinstance(body_content, str) else body_content
            
            # Return the analysis report if available
            if "analysisReport" in analysis_data:
                return f"Financial Analysis for {ticker.upper()}:\n\n{analysis_data['analysisReport']}"
            else:
                return f"Analysis data retrieved for {ticker.upper()}: {json.dumps(analysis_data, indent=2)}"
                
        except Exception as e:
            logger.error(f"Error in local financial analysis wrapper: {str(e)}")
            return f"Error retrieving financial analysis for {ticker}: {str(e)}"
    
    def start_analysis_chat(self, initial_message: str = None):
        """
        Start the financial analysis chat session
        
        Args:
            initial_message: Optional initial message to start the conversation
        """
        if not initial_message:
            initial_message = """🤖 Welcome to the LOCAL AutoGen Financial Analysis System (MOCK MODE)! 

I can help you analyze stocks using comprehensive fundamental analysis simulated locally.
Just provide a stock ticker symbol (e.g., AAPL, TSLA, MSFT) and I'll:
 
1. 🔍 Retrieve mocked financial metrics (no external calls)
2. 📊 Calculate fundamental analysis scores using local logic  
3. 💰 Provide valuation assessment with Claude AI reasoning
4. 🎯 Give investment recommendations (for informational purposes only)
 
✨ This system runs 100% locally with MOCK data - no AWS, no Pinecone.
 
What stock would you like me to analyze?"""
        
        # Start the group chat
        group_chat = autogen.GroupChat(
            agents=[self.user_proxy, self.financial_analyst, self.data_researcher],
            messages=[],
            max_round=20,
            speaker_selection_method="round_robin"
        )
        
        manager = autogen.GroupChatManager(
            groupchat=group_chat,
            llm_config={"config_list": [{"model": "claude-3-5-sonnet-20241022", "api_key": self.lambda_adapter.anthropic_api_key, "api_type": "anthropic"}]}
        )
        
        # Start the conversation
        self.user_proxy.initiate_chat(
            manager,
            message=initial_message
        )
    
    def analyze_single_stock(self, ticker: str) -> str:
        """
        Analyze a single stock and return the results
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Analysis results
        """
        return self.get_financial_analysis_wrapper(ticker)

def main():
    """Main function to run the AutoGen financial analysis system with LOCAL execution"""
    
    # Configuration - Only Anthropic API key needed for local execution
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not found in environment variables.")
        print("Please set your Anthropic API key to use Claude.")
        print("You can get one from: https://console.anthropic.com/")
        return
    
    # Initialize the system (mock-only build; no AWS Lambda or external data sources)
    try:
        analysis_system = FinancialAnalysisAutoGenSystem(
            anthropic_api_key=ANTHROPIC_API_KEY,
            use_mock_data=True
        )
        
        print("🎉 AutoGen Financial Analysis System initialized successfully!")
        print("🏠 Using 100% MOCK financial data (no AWS or external APIs)")
        print("🤖 Using Anthropic Claude for intelligent analysis")
        print("📊 No Pinecone/AWS calls are performed in this build")
        
        # Start the interactive chat
        analysis_system.start_analysis_chat()
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {str(e)}")
        print(f"❌ Error: {str(e)}")
        print("💡 Make sure you have:")
        print("   - Valid ANTHROPIC_API_KEY in .env file")
        print("   - PINECONE_API_KEY in .env file")  
        print("   - All dependencies installed: pip install -r requirements.txt")

if __name__ == "__main__":
    main()