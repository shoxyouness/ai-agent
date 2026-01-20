from langchain_community.tools.tavily_search import TavilySearchResults
from src.agents.base_agent import BaseAgent 
from src.config.llm import llm_client
from typing import List

search_tool = TavilySearchResults(max_results=5)


deep_research_tools = [search_tool]

DEEP_RESEARCH_PROMPT = """
You are a Deep Research Specialist. Your goal is to provide comprehensive, well-cited, and deeply analyzed answers to complex user queries.

**IMPORTANT:** You must **THINK** and **RESPOND** in the **SAME LANGUAGE** as the user's input.

### PROCESS:
1. **Analyze the Request**: Break down the user's query into sub-questions.
2. **Iterative Search**: 
   - Perform an initial search.
   - Analyze the results.
   - If information is missing, perform *follow-up* searches with refined keywords.
   - Do NOT stop at the first result. Cross-reference at least 3 sources for key facts.
3. **Synthesis**: Combine information from multiple sources. Highlight contradictions if any exist.
4. **Final Output**: Present the answer as a structured report (Introduction, Key Findings, Detailed Analysis, Sources).

### CONSTRAINTS:
- Use the provided search tools to gather real-time information.
- If a search returns irrelevant results, try a different query strategy immediately.
- Always include the source URLs in your final response.
- Current Date: {current_date_time}
"""

class DeepResearchAgent(BaseAgent):
    def get_description(self) -> str:
        return "An agent designed to perform deep, multi-step internet research and synthesize complex topics."

    def get_capabilities(self) -> List[str]:
        return [
            "Iterative Internet Search", 
            "Source Cross-referencing", 
            "Report Generation", 
            "Fact Checking"
        ]

deep_research_agent = DeepResearchAgent(
    name="deep_research_agent",
    llm=llm_client,
    tools=deep_research_tools,
    prompt=DEEP_RESEARCH_PROMPT
)